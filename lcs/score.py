import osmnx as ox
import networkx as nx
import pandas as pd
import taxicab

MAX_LCS = 77
WALKING_SPEED_MS = 0.8 # meters per second
INFRASTRUCTURE_CUTOFF_DIST = 20 # meters

# Source: https://wiki.openstreetmap.org/wiki/Key:building?uselang=en-GB#Accommodation
# Source: https://wiki.openstreetmap.org/wiki/Key:shop / https://wiki.openstreetmap.org/wiki/Key:amenity?uselang=en-GB
RESIDENTIAL_TAGS = {'building': ['apartments', 'bungalow', 'cabin', 'detached', 'dormitory', 'house', 'residential', 'semidetached_house', 'yes']}

# Structure: (<feature name>, <max score>, <filtering tags>)
AMENITY_TAGS = [
    # Public Transport
    ('public_transport', 5, {'public_transport': True}),
    # Bicycle Rental
    ('bike_rental', 2, {'amenity': ['bicycle_rental', 'kick-scooter_rental', 'escooter_rental']}),
    # Grocer
    ('grocer', 3, {'shop': ['supermarket', 'butcher', 'cheese', 'convenience', 'deli', 'dairy', 'greengrocer', 'health_food', 'department_store', 'general']}),
    # Pharmacy
    ('pharmacy', 3, {'shop': ['chemist'], 'amenity': ['pharmacy'], 'healthcare': ['pharmacy']}),
    # Bank
    ('bank', 2, {'amenity': ['bank', 'atm'], 'atm': True}),
    # Playground
    ('playground', 2, {'leisure': ['playground', 'pitch', 'track']}),
    # General Store
    ('general_store', 2, {'shop': ['supermarket', 'convenience', 'deli', 'greengrocer', 'health_food', 'department_store', 'general']}),
    # Clothes Store
    ('clothes_store', 2, {'shop': ['clothes', 'shoes']}),
    # Kindergarten
    ('kindergarten', 2, {'amenity': ['kindergarten'], 'building': ['kindergarten']}),
    # School
    ('school', 4, {'amenity': ['school'], 'building': ['school']}),
    # Restaurant
    ('restaurant', 2, {'amenity': ['restaurant', 'food_court', 'fast_food']}),
    # Cafe
    ('cafe', 2, {'amenity': ['cafe'], 'scop': ['coffee']}),
    # Dry Cleaner
    ('cleaner', 2, {'shop': ['dry_cleaning', 'laundry']}),
    # Beauty and grooming
    ('beauty', 2, {'shop': ['beauty', 'hairdresser']}),
    # Outdoor physical activities
    ('outdoor_sports', 2, {'leisure': ['disc_golf_course', 'dog_park', 'fishing', 'fitness_station', 'golf_course', 'horse_riding', 'pitch', 'stadium', 'track', 'stadium', 'swimming_area', 'water_park']}),
    # Indoor physical activities
    ('indoor_sports', 2, {'leisure': ['bowling_alley', 'dance', 'fitness_centre', 'ice_rink', 'sports_centre', 'sports_hall', 'swimming_pool', 'trampoline_park', 'water_park'], 'sport': ['gym']}),
    # Entertainment venue
    ('entertainment', 1, {
        'leisure': ['adult_gaming_centre', 'amusement_arcade', 'dance', 'miniature_golf'], 
        'amenity': ['arts_centre', 'casino', 'cinema', 'community_centre', 'conference_centre', 'events_venue', 'exhibition_centre', 'music_venue', 'nightclub', 'social_centre', 'theatre']
        }),
    # Hospital or clinic
    ('hospital', 1, {'amenity': ['clinic', 'hospital', 'doctors']}),
    # Bookstore or library
    ('bookstore', 1, {'shop': ['books'], 'amenity': ['library']}),
    # Museum
    ('museum', 1, {'tourism': ['museum', 'aquarium', 'zoo']}),
    # Art Gallery
    ('art_gallery', 1, {'tourism': ['artwork', 'gallery']}),
    # Park
    ('park', 2, {'leisure': ['park']}),
]

PARKING_TAGS = ['parking:left', 'parking:right', 'parking:both']
CYCLEWAY_BUFFER_TAGS = ['cycleway:buffer', 'cycleway:left:buffer', 'cycleway:right:buffer', 'cycleway:both:buffer']
ACCESSIBLE_TAGS = ['tactile_paving', 'wheelchair']

ox.config(useful_tags_way=['width', 'lit', 'maxspeed'] + PARKING_TAGS + CYCLEWAY_BUFFER_TAGS + ACCESSIBLE_TAGS)

class LCSQueryEngine:
    def __init__(self, config):
        self.config = config

        self.place_id = config['placeId']
        self.defaults = config.get('defaults', {})
        self.globals = config.get('globals', {})

        self.default_maxspeed = self.defaults.get('maxspeed', 50.0)
        self.default_sidewalk_width = self.defaults.get('sidewalk_width', 1.0)
        self.default_sidewalk_lit = self.defaults.get('sidewalk_lit', "no")
        self.default_bikepath_width = self.defaults.get('bike_width', 1.0)
        self.default_bikepath_lit = self.defaults.get('bike_lit', "no")

    def query_features_with_lcs(self):
        print ("  -> Querying residential buildings...")

        df_residential = ox.features_from_place(self.place_id, RESIDENTIAL_TAGS)
        df_residential = ox.projection.project_gdf(df_residential)
        df_residential = df_residential[df_residential['shop'].isnull()]
        df_residential = df_residential[df_residential['amenity'].isnull()]
        df_residential = df_residential[df_residential['leisure'].isnull()]
        df_residential = df_residential[df_residential['tourism'].isnull()]
        df_residential = df_residential[df_residential['office'].isnull()]
        df_residential = df_residential.reset_index()

        print ("  -> Querying graphs...")

        df_path_walk = self._safe_query_graph(network_type='walk')
        df_path_bike = nx.compose(
            self._safe_query_graph(custom_filter='["highway"~"cycleway"]'), 
            self._safe_query_graph(custom_filter='["cycleway"~"track"]')
        )
        df_path_drive = self._safe_query_graph(network_type='drive')
        # df_path_all = ox.graph_from_place(self.place_id, simplify=True)

        print ("  -> Calculating graph-based scores...")

        df_residential['edges_walk'], df_residential['edges_walk_dist'] = ox.nearest_edges(df_path_walk, df_residential.centroid.x, df_residential.centroid.y, return_dist=True)
        df_residential['edges_bike'], df_residential['edges_bike_dist'] = ox.nearest_edges(df_path_bike, df_residential.centroid.x, df_residential.centroid.y, return_dist=True)
        df_residential['edges_drive'], df_residential['edges_drive_dist'] = ox.nearest_edges(df_path_drive, df_residential.centroid.x, df_residential.centroid.y, return_dist=True)

        df_residential['edges_walk'] = df_residential['edges_walk'].apply(lambda n: df_path_walk.edges[n])
        df_residential['edges_bike'] = df_residential['edges_bike'].apply(lambda n: df_path_bike.edges[n])
        df_residential['edges_drive'] = df_residential['edges_drive'].apply(lambda n: df_path_drive.edges[n])

        df_residential["lcs_sidewalk"] = df_residential.apply(self._sidewalk_score, axis=1)
        df_residential["lcs_bike_path"] = df_residential.apply(self._bike_path_score, axis=1)
        df_residential["lcs_drive_path"] = df_residential.apply(self._drive_path_score, axis=1)

        for feature_name, score, tags in AMENITY_TAGS:
            print (f"  -> Calculating scores for {feature_name} amenity...")

            df = self._safe_query_locations(tags)

            if df.empty:
                df_residential[f"lcs_{feature_name}"] = 0  
                continue

            df_nearest = df_residential.sjoin_nearest(df, distance_col='dist', how='inner')

            # df_dist = score * df_joined.apply(lambda x: calculate_walking_distance(df, x), axis=1).apply(distance_to_score)
            df_dist = score * df_nearest['dist'].apply(self._distance_to_score)
            df_dist = df_dist.groupby(df_dist.index).min()
            df_residential[f"lcs_{feature_name}"] = df_dist

        df_residential['lcs'] = 0

        if self.globals['yearly_aqi'] <= 150:
            df_residential['lcs_air_quality'] = 3

        for col in [col for col in df_residential.columns if col.startswith("lcs_")]:
            df_residential['lcs'] += df_residential[col]

        df_residential['lcs_perc'] = df_residential['lcs'] * 1.0 / MAX_LCS * 100

        return df_residential

    def _distance_to_score(self, distance):
        min_time = distance / WALKING_SPEED_MS / 60

        if min_time > 25:
            return 0

        return min((25 - min_time) / 20, 1)

    def _calculate_walking_distance(self, df_dest, node):
        node_dest = df_dest[df_dest.index == node['index_right']]['geometry'].values[0].centroid
        node_source = node['geometry'].centroid

        try:
            path = taxicab.distance.shortest_path(
                df_path_all, 
                (node_dest.y, node_dest.x), 
                (node_source.y, node_source.x)
            )

            return path[0]
        except BaseException as ex:
            print (ex)
            return ox.distance.euclidean_dist_vec(node_dest.y, node_dest.x, node_source.y, node_source.x)

    def _sidewalk_score(self, node):
        total_score = 0

        if node.get('edges_walk_dist', 1000) < INFRASTRUCTURE_CUTOFF_DIST:
            closest_street = node['edges_walk']
            sidewalk_width = self._get_width(closest_street, 'width', self.default_sidewalk_width)

            if sidewalk_width < 1:
                return total_score
            
            total_score += 3

            if sidewalk_width >= 2:
                total_score += 1

            if self._get_value(closest_street, "lit", self.default_sidewalk_lit) == 'yes':
                total_score += 1 

            if self._has_any_tag(node, ACCESSIBLE_TAGS):
                total_score += 2

            if self._get_value(closest_street, "noise_db", 60) < 65:
                total_score += 3

            if self._get_value(closest_street, "shaded", "no") == 'yes':
                total_score += 3

        return total_score

    def _bike_path_score(self, node):
        total_score = 0

        if node.get('edges_bike_dist', 1000) < INFRASTRUCTURE_CUTOFF_DIST:
            closest_path = node['edges_bike']

            if float(self._get_width(closest_path, 'width', self.default_bikepath_width)) < 1.5:
                return total_score
            
            total_score += 3

            if self._get_value(closest_path, "lit", self.default_bikepath_lit) == 'yes':
                total_score += 1 

            if self._has_any_tag(node, CYCLEWAY_BUFFER_TAGS):
                total_score += 1

        return total_score

    def _drive_path_score(self, node):
        total_score = 0

        if node.get('edges_drive_dist', 1000) < INFRASTRUCTURE_CUTOFF_DIST:
            closest_street = node['edges_drive']
            max_speed = self._get_speed(node, 'maxspeed', self.default_maxspeed)

            if self._get_value(closest_street, "traffic_calming", "no") == 'yes':
                total_score += 2

            if max_speed <= 30:
                total_score += 2

            if max_speed <= 15:
                total_score += 1 

            if self._get_value(closest_street, "no_parking_enforced", "no") == 'yes':
                total_score += 1

            if self._has_any_tag(node, PARKING_TAGS):
                total_score += 1

        return total_score
    
    def _get_speed(self, node, attr_name, default_value):
        max_speed = self._get_value(node, attr_name, default_value)

        if type(max_speed) is str:
            max_speed = max_speed.lower()

        if max_speed in self.config["parameters"]:
            max_speed = self.config["parameters"][max_speed]
        
        if type(max_speed) is str:
            try:
                max_speed = float(max_speed)
            except BaseException as ex:
                max_speed = default_value
        
        return max_speed
    
    def _get_width(self, node, attr_name, default_value):
        width = self._get_value(node, attr_name, default_value)

        if type(width) is str:
            width = width.lower()

            if width.endswith("m"):
                width = width[:-1].strip()

            try:
                width = float(width)
            except BaseException as ex:
                width = width
        
        return width
    
    def _get_value(self, node, attr_name, default_value=None):
        val = node.get(attr_name, default_value)

        if type(val) is list:
            val = val[0]

        return val
    
    def _has_any_tag(self, node, tags):
        for tag in tags:
            if node.get(tag, 'no') != 'no':
                return True
        
        return False

    def _safe_query_graph(self, network_type=None, custom_filter=None):
        try:
            df = ox.graph_from_place(self.place_id, custom_filter=custom_filter, network_type=network_type, retain_all=True, simplify=True)
            return ox.project_graph(df)
        except ValueError as ex:
            print (ex)
            return nx.multidigraph.MultiDiGraph()
        
    def _safe_query_locations(self, tags):
        try:
            df = ox.features_from_place(self.place_id, tags).reset_index()
            df = ox.projection.project_gdf(df)
            return df
        except ox._errors.InsufficientResponseError as ex:
            print (ex)
            return pd.DataFrame()