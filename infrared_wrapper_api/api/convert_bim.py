## file just for testing of functions, will be removed

import geopandas as gpd
import pyvista as pv
import shapely
from dotbimpy import *
import uuid

filename = 'geoJson-Leipzig-01102024'
path_buildings = f'infrared_wrapper_api/models/jsons/{filename}.json'
gdf = gpd.read_file(path_buildings)


def convert_geojsons(gdf: gpd.GeoDataFrame, height_col: str):
    gdf = gdf.rename(columns={height_col:'building_height'})
    gdf = gdf.loc[~gdf['building_height'].isna()]
    gdf = gdf.explode()
    gdf = gdf.to_crs('EPSG:25832')
    centroid = gdf['geometry'].union_all().centroid
    centroid = shapely.get_coordinates(centroid).tolist()[0]
    c_x = centroid[0]
    c_y = centroid[1]
    meshes = []
    elements = []

    counter = 0
    for _, row in gdf.iterrows():
        geometry = row['geometry']
        height = row['building_height']

        # Skip invalid or empty geometries
        if geometry.is_empty or not geometry.is_valid:
            print("Skipping invalid or empty geometry")
            continue

        # Fix precision issues and check area
        geometry = geometry.buffer(0)
        if geometry.area == 0 or len(geometry.exterior.coords) < 3:
            print("Skipping degenerate or zero-area geometry")
            continue

        # Remove duplicate closing point
        exterior = [(x-c_x, y-c_y, 0) for x, y in geometry.exterior.coords]
        if exterior[0] == exterior[-1]:
            exterior = exterior[:-1]

        # Check bounds to skip degenerate polygons
        x_coords, y_coords = zip(*[(x, y) for x, y, _ in exterior])
        if max(x_coords) - min(x_coords) == 0 or max(y_coords) - min(y_coords) == 0:
            print("Degenerate geometry: all points lie on a line or single point")
            continue    

        # Create and triangulate PolyData
        base_polygon = pv.PolyData(exterior).delaunay_2d()
        
        extrusion = base_polygon.extrude([0, 0, height], capping=True)
        extrusion = extrusion.triangulate()
        

        extrusion = extrusion.extract_surface()
        coordinates = extrusion.points.flatten().tolist()
        indices = extrusion.faces.reshape(-1, 4)[:, 1:].flatten().tolist()  # Skip the face counts

        vector = Vector(x=0,y=0,z=0)
        rotation = Rotation(qx=0, qy=0, qz=0, qw=1.0)
        geomtype = 'Block'
        color = Color(r=120, g=166, b=171, a=180)
        info = {'Name':f'building-{counter}'}
        guid = str(uuid.uuid4())

        mesh = Mesh(mesh_id=counter,coordinates=coordinates,indices=indices)
        element = Element(mesh_id=counter,vector=vector,rotation=rotation,guid=guid,type=geomtype,color=color,info=info)
        meshes.append(mesh)
        elements.append(element)
        counter=counter+1

    file_info = {
        "Author":"DCS"
    }

    file = File("1.0.0",meshes=meshes,elements=elements,info=file_info)
    file.save(f"{filename}.bim")

def transform_to_bim(gdf: gpd.GeoDataFrame):
    """
    Transforms a GeoDataFrame to BIM geometries with extrusion and triangulation.

    Parameters:
        gdf (gpd.GeoDataFrame): Input GeoDataFrame with 'building_height' and 'geometry'.

    Returns:
        dict: A dictionary containing BIM geometry data keyed by unique GUIDs.
    """
    # Filter out rows with missing building heights and convert CRS
    gdf = gdf.loc[~gdf['building_height'].isna()]
    gdf = gdf.explode()
    gdf = gdf.to_crs('EPSG:25832')

    # Calculate the centroid of all geometries
    centroid = gdf['geometry'].unary_union.centroid
    c_x, c_y = shapely.get_coordinates(centroid).tolist()[0]

    geometries = {}
    counter = 0

    for _, row in gdf.iterrows():
        geometry = row['geometry']
        height = row['building_height']

        # Skip invalid or empty geometries
        if not geometry.is_valid or geometry.is_empty:
            print("Skipping invalid or empty geometry")
            continue

        # Fix precision issues and check for valid area
        geometry = geometry.buffer(0)
        if geometry.area == 0 or len(geometry.exterior.coords) < 3:
            print("Skipping degenerate or zero-area geometry")
            continue

        # Adjust coordinates relative to centroid and remove duplicate closing point
        exterior = [(x - c_x, y - c_y, 0) for x, y in geometry.exterior.coords[:-1]]

        # Ensure geometry is not degenerate (e.g., all points in a line)
        x_coords, y_coords = zip(*[(x, y) for x, y, _ in exterior])
        if max(x_coords) - min(x_coords) == 0 or max(y_coords) - min(y_coords) == 0:
            print("Degenerate geometry: all points lie on a line or single point")
            continue

        # Create base polygon and perform 2D triangulation
        try:
            base_polygon = pv.PolyData(exterior).delaunay_2d()
        except Exception as e:
            print(f"Error in triangulation: {e}")
            continue

        # Extrude the polygon to create 3D geometry
        extrusion = base_polygon.extrude([0, 0, height], capping=True).triangulate().extract_surface()

        # Collect mesh data
        coordinates = extrusion.points.flatten().tolist()
        indices = extrusion.faces.reshape(-1, 4)[:, 1:].flatten().tolist()  # Skip the face counts
        guid = str(uuid.uuid4())

        geometries[guid] = {
            "mesh_id": counter,
            "coordinates": coordinates,
            "indices": indices
        }

        counter += 1

    return geometries

#geoms = transform_to_bim(gdf=gdf)
convert_geojsons(gdf=gdf,height_col='building_height')

# with open(f"{filename}-request.json","w") as f:
#     json.dump(geoms,f,indent=4)