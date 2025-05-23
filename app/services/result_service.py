from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Dict, Any, Optional 
from collections import defaultdict

from app.models.race_result import RaceResult
from app.models.registration import Registration
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance
from app.models.strava_user import StravaUserDB
from app.schemas.race_result import RaceResultRead
from app.schemas.registration import RegistrationReadMinimal # For RaceResultRead
from app.schemas.strava_user import UserRead as UserSchema # For RegistrationReadMinimal

async def get_event_results_classified(
    db: AsyncSession, event_id: int
) -> Dict[str, Dict[str, List[RaceResultRead]]]:
    stmt = (
        select(RaceResult)
        .join(RaceResult.registration)
        .join(Registration.category)
        .join(Registration.distance)
        .join(Registration.user) 
        .where(Registration.event_id == event_id)
        .where(RaceResult.net_time_seconds.isnot(None)) 
        .order_by(EventCategory.name, EventDistance.distance_km, RaceResult.net_time_seconds.asc())
        .options(
            joinedload(RaceResult.registration).joinedload(Registration.user),
            joinedload(RaceResult.registration).joinedload(Registration.category),
            joinedload(RaceResult.registration).joinedload(Registration.distance)
        )
    )
    
    results = await db.execute(stmt)
    race_results_models = results.scalars().all()

    classified_results: Dict[str, Dict[str, List[RaceResultRead]]] = defaultdict(lambda: defaultdict(list))

    for rr_model in race_results_models:
        category_name = rr_model.registration.category.name
        distance_km_str = f"{rr_model.registration.distance.distance_km} km"
        
        user_schema = None
        if rr_model.registration and rr_model.registration.user:
            user_schema = UserSchema.model_validate(rr_model.registration.user)

        reg_minimal_schema = None
        if rr_model.registration:
            # Pass the populated user schema to RegistrationReadMinimal
            update_data_reg = {}
            if user_schema:
                update_data_reg['user'] = user_schema
            
            reg_minimal_schema = RegistrationReadMinimal.model_validate(
                rr_model.registration, 
                update=update_data_reg 
            )

        # Pass populated registration schema to RaceResultRead
        update_data_rr = {}
        if reg_minimal_schema:
            update_data_rr['registration'] = reg_minimal_schema

        rr_schema = RaceResultRead.model_validate(
            rr_model,
            update=update_data_rr 
        )
        classified_results[category_name][distance_km_str].append(rr_schema)
           
    return dict(classified_results)

# --- Leaderboard specific imports and constants ---
from app.models.virtual_result import VirtualResult
# from app.schemas.virtual_result import VirtualResultRead # Not directly used but good for reference
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, extract # Ensure extract is imported

# Define standard distances for leaderboards (in km)
STANDARD_DISTANCES_KM = [1.0, 3.0, 5.0, 7.0, 10.0, 12.0]
# Define a tolerance for matching activity distances to standard distances
DISTANCE_TOLERANCE_KM = 0.1 # e.g., 5km +/- 0.1km

async def get_yearly_leaderboard(
    db: AsyncSession, 
    year: Optional[int] = None, 
    top_n: int = 10
) -> Dict[str, List[Dict[str, Any]]]:
    leaderboard: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    processed_results_for_leaderboard = []

    # --- Query RaceResults ---
    race_results_query = (
        select(
            RaceResult.net_time_seconds,
            Registration.user_strava_id,
            EventDistance.distance_km,
            Event.name.label("event_name"),
            Event.date.label("activity_date"),
            StravaUserDB.firstname,
            StravaUserDB.lastname
        )
        .join(RaceResult.registration)
        .join(Registration.user)
        .join(Registration.event)
        .join(Registration.distance)
        .where(RaceResult.net_time_seconds.isnot(None))
    )
    if year:
        race_results_query = race_results_query.where(
            extract('year', Event.date) == year
        )
    
    race_results_db = (await db.execute(race_results_query)).mappings().all()
    for res_data in race_results_db:
        processed_results_for_leaderboard.append({**res_data, 'source': 'Race'})


    # --- Query VirtualResults ---
    virtual_results_query = (
        select(
            VirtualResult.elapsed_time_seconds.label("net_time_seconds"),
            VirtualResult.user_strava_id,
            VirtualResult.distance_km,
            VirtualResult.name.label("event_name"), # Using activity name as event_name
            VirtualResult.activity_date,
            StravaUserDB.firstname,
            StravaUserDB.lastname
        )
        .join(VirtualResult.user) # Assuming VirtualResult.user is the relationship to StravaUserDB
        .where(VirtualResult.elapsed_time_seconds.isnot(None))
    )
    if year:
        virtual_results_query = virtual_results_query.where(
            extract('year', VirtualResult.activity_date) == year
        )
    
    virtual_results_db = (await db.execute(virtual_results_query)).mappings().all()
    for res_data in virtual_results_db:
        processed_results_for_leaderboard.append({**res_data, 'source': 'Virtual'})
    
    # Process results for each standard distance
    for std_dist_km in STANDARD_DISTANCES_KM:
        candidate_results = []
        for res_data in processed_results_for_leaderboard:
            # Check if res_data['distance_km'] is not None before comparison
            if res_data['distance_km'] is not None and \
               abs(res_data['distance_km'] - std_dist_km) <= DISTANCE_TOLERANCE_KM:
                
                pace_seconds_per_km = None
                if res_data['distance_km'] > 0 and res_data['net_time_seconds'] is not None:
                    pace_seconds_per_km = res_data['net_time_seconds'] / res_data['distance_km']
                
                candidate_results.append({
                    "athlete_name": f"{res_data.get('firstname', '') or ''} {res_data.get('lastname', '') or ''}".strip(),
                    "user_strava_id": res_data['user_strava_id'],
                    "time_seconds": res_data['net_time_seconds'],
                    "actual_distance_km": res_data['distance_km'],
                    "pace_seconds_per_km": pace_seconds_per_km,
                    "event_name": res_data['event_name'],
                    "activity_date": res_data['activity_date'].strftime('%Y-%m-%d') if res_data['activity_date'] else 'N/A',
                    "source": res_data['source']
                })

        # Sort by pace (handling None), then by time as a tie-breaker
        candidate_results.sort(key=lambda x: (x['pace_seconds_per_km'] is None, x['pace_seconds_per_km'], x['time_seconds']))

        best_user_results = {} # Store the best result for each user for this distance
        for res in candidate_results:
            user_id = res['user_strava_id']
            # Only consider results with a valid pace for comparison, unless user has no paced results yet
            if res['pace_seconds_per_km'] is not None:
                if user_id not in best_user_results or \
                   best_user_results[user_id]['pace_seconds_per_km'] is None or \
                   res['pace_seconds_per_km'] < best_user_results[user_id]['pace_seconds_per_km']:
                    best_user_results[user_id] = res
            elif user_id not in best_user_results: # If user has no paced result yet, store this one (even if unpaced for now)
                 best_user_results[user_id] = res

        # Get the top N results from the best user results
        top_results_for_distance = sorted(
            list(best_user_results.values()), 
            key=lambda x: (x['pace_seconds_per_km'] is None, x['pace_seconds_per_km'], x['time_seconds'])
        )[:top_n]
        
        leaderboard[f"{std_dist_km} km"] = top_results_for_distance
           
    return dict(leaderboard)


async def get_user_personal_bests(
    db: AsyncSession,
    user_strava_id: int
) -> Dict[str, Dict[str, Any]]: # Key: "5.0 km", Value: best result dict
    # Calculates a user's personal best performances for standard distances.
    # Considers both their RaceResult and VirtualResult.
    personal_bests: Dict[str, Dict[str, Any]] = {}

    # --- Query RaceResults for the user ---
    race_results_query = (
        select(
            RaceResult.net_time_seconds,
            EventDistance.distance_km,
            Event.name.label("event_name"),
            Event.date.label("activity_date")
        )
        .join(RaceResult.registration)
        .join(Registration.event) # Event is joined from Registration
        .join(Registration.distance) # EventDistance is joined from Registration
        .where(Registration.user_strava_id == user_strava_id)
        .where(RaceResult.net_time_seconds.isnot(None))
    )
    user_race_results = (await db.execute(race_results_query)).mappings().all()

    # --- Query VirtualResults for the user ---
    virtual_results_query = (
        select(
            VirtualResult.elapsed_time_seconds.label("net_time_seconds"),
            VirtualResult.distance_km,
            VirtualResult.name.label("event_name"),
            VirtualResult.activity_date
        )
        .where(VirtualResult.user_strava_id == user_strava_id)
        .where(VirtualResult.elapsed_time_seconds.isnot(None))
    )
    user_virtual_results = (await db.execute(virtual_results_query)).mappings().all()

    all_user_activities = []
    for res_data in user_race_results:
        all_user_activities.append({**res_data, 'source': 'Race'})
    for res_data in user_virtual_results:
        all_user_activities.append({**res_data, 'source': 'Virtual'})
    
    for std_dist_km in STANDARD_DISTANCES_KM:
        best_result_for_std_dist = None
        current_best_pace = float('inf')

        for activity in all_user_activities:
            activity_dist_km = activity.get('distance_km')
            activity_time_sec = activity.get('net_time_seconds')

            if activity_dist_km is None or activity_time_sec is None:
                continue

            if abs(activity_dist_km - std_dist_km) <= DISTANCE_TOLERANCE_KM:
                if activity_dist_km > 0: # Avoid division by zero
                    pace_seconds_per_km = activity_time_sec / activity_dist_km
                    
                    if pace_seconds_per_km < current_best_pace:
                        current_best_pace = pace_seconds_per_km
                        best_result_for_std_dist = {
                            "time_seconds": activity_time_sec,
                            "actual_distance_km": activity_dist_km,
                            "pace_seconds_per_km": pace_seconds_per_km,
                            "event_name": activity['event_name'],
                            "activity_date": activity['activity_date'].strftime('%Y-%m-%d') if activity['activity_date'] else 'N/A',
                            "source": activity['source']
                        }
        
        if best_result_for_std_dist:
            personal_bests[f"{std_dist_km} km"] = best_result_for_std_dist
            
    return personal_bests
