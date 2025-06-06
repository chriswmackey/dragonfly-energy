# coding=utf-8
import pytest
import os
import json

from ladybug_geometry.geometry3d import Vector3D, Point3D, Plane, Face3D
from ladybug.location import Location
from ladybug.futil import nukedir

import honeybee.model as hb_model
from honeybee_energy.lib.programtypes import office_program, plenum_program
import honeybee_energy.lib.scheduletypelimits as schedule_types
from honeybee_energy.lib.materials import roof_membrane, wood, insulation
from honeybee_energy.constructionset import ConstructionSet
from honeybee_energy.construction.opaque import OpaqueConstruction
from honeybee_energy.construction.window import WindowConstruction
from honeybee_energy.construction.shade import ShadeConstruction
from honeybee_energy.construction.air import AirBoundaryConstruction
from honeybee_energy.material._base import _EnergyMaterialBase
from honeybee_energy.material.opaque import EnergyMaterial
from honeybee_energy.schedule.ruleset import ScheduleRuleset
from honeybee_energy.load.lighting import Lighting

from dragonfly.model import Model
from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.context import ContextShade
from dragonfly.windowparameter import SimpleWindowRatio

from dragonfly_energy.properties.model import ModelEnergyProperties
from dragonfly_energy.opendss.network import ElectricalNetwork
from dragonfly_energy.des.loop import GHEThermalLoop


def test_energy_properties():
    """Test the existence of the Model energy properties."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    building = Building('OfficeBuilding', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])
    bright_leaves = ShadeConstruction('Bright Light Leaves', 0.5, 0.5, True)
    tree_canopy.properties.energy.construction = bright_leaves
    tree_trans = ScheduleRuleset.from_constant_value(
        'Tree Transmittance', 0.5, schedule_types.fractional)
    tree_canopy.properties.energy.transmittance_schedule = tree_trans

    model = Model('NewDevelopment', [building], [tree_canopy])

    assert hasattr(model.properties, 'energy')
    assert isinstance(model.properties.energy, ModelEnergyProperties)
    assert isinstance(model.properties.host, Model)
    assert len(model.properties.energy.materials) == 0
    for mat in model.properties.energy.materials:
        assert isinstance(mat, _EnergyMaterialBase)
    assert len(model.properties.energy.constructions) == 1
    for cnst in model.properties.energy.constructions:
        assert isinstance(
            cnst, (WindowConstruction, OpaqueConstruction,
                   ShadeConstruction, AirBoundaryConstruction))
    assert len(model.properties.energy.shade_constructions) == 1
    assert len(model.properties.energy.construction_sets) == 0
    assert len(model.properties.energy.schedule_type_limits) == 3
    assert len(model.properties.energy.schedules) == 8
    assert len(model.properties.energy.shade_schedules) == 1
    assert len(model.properties.energy.program_types) == 1


def test_check_duplicate_construction_set_identifiers():
    """Test the check_duplicate_construction_set_identifiers method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()

    constr_set = ConstructionSet('Attic Construction Set')
    polyiso = EnergyMaterial('PolyIso', 0.2, 0.03, 43, 1210, 'MediumRough')
    roof_constr = OpaqueConstruction('Attic Roof Construction',
                                     [roof_membrane, polyiso, wood])
    floor_constr = OpaqueConstruction('Attic Floor Construction',
                                      [wood, insulation, wood])
    constr_set.floor_set.interior_construction = floor_constr
    constr_set.roof_ceiling_set.exterior_construction = roof_constr
    building.unique_room_2ds[-1].properties.energy.construction_set = constr_set
    building.unique_room_2ds[-2].properties.energy.construction_set = constr_set

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building], [tree_canopy])

    assert model.properties.energy.check_duplicate_construction_set_identifiers(False) == ''
    assert model.properties.energy.check_all_duplicate_identifiers(False) == ''

    constr_set2 = ConstructionSet('Attic Construction Set')
    building.unique_room_2ds[-2].properties.energy.construction_set = constr_set2
    assert model.properties.energy.check_duplicate_construction_set_identifiers(False) != ''
    with pytest.raises(ValueError):
        model.properties.energy.check_duplicate_construction_set_identifiers(True)
    assert model.properties.energy.check_all_duplicate_identifiers(False) != ''
    with pytest.raises(ValueError):
        model.properties.energy.check_all_duplicate_identifiers(True)


def test_check_duplicate_program_type_identifiers():
    """Test the check_duplicate_program_type_identifiers method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()

    attic_program_type = plenum_program.duplicate()
    attic_program_type.identifier = 'Attic Space'
    schedule = ScheduleRuleset.from_constant_value(
        'Always Dim', 1, schedule_types.fractional)
    lighting = Lighting('Attic Lighting', 3, schedule)
    attic_program_type.lighting = lighting
    building.unique_room_2ds[-1].properties.energy.program_type = attic_program_type
    building.unique_room_2ds[-2].properties.energy.program_type = attic_program_type

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building], [tree_canopy])

    assert model.properties.energy.check_duplicate_program_type_identifiers(False) == ''
    assert model.properties.energy.check_all_duplicate_identifiers(False) == ''

    attic_program_type.unlock()
    attic_program_type.identifier = office_program.identifier
    attic_program_type.lock()
    assert model.properties.energy.check_duplicate_program_type_identifiers(False) != ''
    with pytest.raises(ValueError):
        model.properties.energy.check_duplicate_program_type_identifiers(True)
    assert model.properties.energy.check_all_duplicate_identifiers(False) != ''
    with pytest.raises(ValueError):
        model.properties.energy.check_all_duplicate_identifiers(True)


def test_check_all_zones_have_one_hvac():
    """Test the check_all_zones_have_one_hvac method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    model = Model('NewDevelopment', [building])

    assert model.properties.energy.check_all_zones_have_one_hvac(False) == ''
    room2d_1.zone = room2d_2.zone = 'Main House'
    assert model.properties.energy.check_all_zones_have_one_hvac(False) != ''
    with pytest.raises(ValueError):
        model.properties.energy.check_all_zones_have_one_hvac(True)
    model.properties.energy.check_all_zones_have_one_hvac(False, True)

    room2d_2.zone = 'Main House2'
    assert model.properties.energy.check_all_zones_have_one_hvac(False) == ''
    for attic in building.unique_stories[-1].room_2ds:
        attic.zone = 'Main House2'
    assert model.properties.energy.check_all_zones_have_one_hvac(False) == ''


def test_check_maximum_elevation():
    """Test the check_maximum_elevation method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()
    model = Model('NewDevelopment', [building])

    assert model.properties.energy.check_maximum_elevation(1000, False) == ''

    model.convert_to_units('Feet')
    model.move(Vector3D(0, 0, 4000))

    assert model.properties.energy.check_maximum_elevation(1000, False) != ''
    with pytest.raises(ValueError):
        model.properties.energy.check_maximum_elevation(1000, True)


def test_to_from_dict():
    """Test the Model to_dict and from_dict method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()

    attic_program_type = plenum_program.duplicate()
    attic_program_type.identifier = 'Attic Space'
    schedule = ScheduleRuleset.from_constant_value(
        'Always Dim', 1, schedule_types.fractional)
    lighting = Lighting('Attic Lighting', 3, schedule)
    attic_program_type.lighting = lighting
    building.unique_room_2ds[-1].properties.energy.program_type = attic_program_type
    building.unique_room_2ds[-2].properties.energy.program_type = attic_program_type

    constr_set = ConstructionSet('Attic Construction Set')
    polyiso = EnergyMaterial('PolyIso', 0.2, 0.03, 43, 1210, 'MediumRough')
    roof_constr = OpaqueConstruction('Attic Roof Construction',
                                     [roof_membrane, polyiso, wood])
    floor_constr = OpaqueConstruction('Attic Floor Construction',
                                      [wood, insulation, wood])
    constr_set.floor_set.interior_construction = floor_constr
    constr_set.roof_ceiling_set.exterior_construction = roof_constr
    building.unique_room_2ds[-1].properties.energy.construction_set = constr_set
    building.unique_room_2ds[-2].properties.energy.construction_set = constr_set

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])
    bright_leaves = ShadeConstruction('Bright Light Leaves', 0.5, 0.5, True)
    tree_canopy.properties.energy.construction = bright_leaves
    tree_trans = ScheduleRuleset.from_constant_value(
        'Tree Transmittance', 0.5, schedule_types.fractional)
    tree_canopy.properties.energy.transmittance_schedule = tree_trans

    model = Model('NewDevelopment', [building], [tree_canopy])

    model_dict = model.to_dict()
    new_model = Model.from_dict(model_dict)
    assert model_dict == new_model.to_dict()

    assert polyiso in new_model.properties.energy.materials
    assert roof_constr in new_model.properties.energy.constructions
    assert floor_constr in new_model.properties.energy.constructions
    assert constr_set in new_model.properties.energy.construction_sets
    assert new_model.buildings[0].unique_room_2ds[-1].properties.energy.construction_set == constr_set

    assert schedule in new_model.properties.energy.schedules
    assert attic_program_type in new_model.properties.energy.program_types
    assert new_model.buildings[0].unique_room_2ds[-1].properties.energy.program_type == attic_program_type

    assert bright_leaves in new_model.properties.energy.constructions
    assert tree_trans in new_model.properties.energy.schedules
    assert new_model.context_shades[0].properties.energy.construction == bright_leaves
    assert new_model.context_shades[0].properties.energy.transmittance_schedule == tree_trans


def test_to_from_dict_plenum_construction():
    """Test the Model to_dict and from_dict method with plenum constructions."""
    # simple 10 x 10 rooms
    pts1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts2 = (Point3D(10, 0, 0), Point3D(20, 0, 0), Point3D(20, 10, 0), Point3D(10, 10, 0))

    # Two rooms with different floor heights
    room2d_full = Room2D(
        'R1-full', floor_geometry=Face3D(pts1), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum = Room2D(
        'R2-plenum', floor_geometry=Face3D(pts2), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum.ceiling_plenum_depth = 0.5
    room2d_plenum.floor_plenum_depth = 0.5

    story = Story('S1', [room2d_full, room2d_plenum])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])

    concrete = EnergyMaterial('Concrete', 0.15, 2.31, 2322, 832, 'MediumRough',
                              0.95, 0.75, 0.8)
    gypsum = EnergyMaterial('Gypsum', 0.0127, 0.16, 784.9, 830, 'MediumRough',
                            0.93, 0.6, 0.65)
    ceil_constr = OpaqueConstruction('Gypsum Ceiling', [gypsum])
    floor_constr = OpaqueConstruction('Concrete Floor', [concrete])
    building.properties.energy.ceiling_plenum_construction = ceil_constr
    building.properties.energy.floor_plenum_construction = floor_constr

    plenum_model = building.to_honeybee(tolerance=0.01)
    plenum_rooms = plenum_model.rooms
    assert len(plenum_rooms) == 4
    plenum = plenum_rooms[0]
    assert plenum[-1].properties.energy.construction == floor_constr
    plenum = plenum_rooms[-1]
    assert plenum[0].properties.energy.construction == ceil_constr

    model = Model('NewDevelopment', [building])
    model_dict = model.to_dict()
    new_model = Model.from_dict(model_dict)
    assert model_dict == new_model.to_dict()
    new_building = new_model.buildings[0]
    assert new_building.properties.energy.ceiling_plenum_construction == ceil_constr
    assert new_building.properties.energy.floor_plenum_construction == floor_constr


def test_to_honeybee():
    """Test the Model to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('OfficeFloorBig', [room2d_3])
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('OfficeBuildingBig', [story_big])
    building_big.separate_top_bottom_floors()

    attic_program_type = plenum_program.duplicate()
    attic_program_type.identifier = 'Attic Space'
    schedule = ScheduleRuleset.from_constant_value(
        'Always Dim', 1, schedule_types.fractional)
    lighting = Lighting('Attic Lighting', 3, schedule)
    attic_program_type.lighting = lighting
    building.unique_room_2ds[-1].properties.energy.program_type = attic_program_type
    building.unique_room_2ds[-2].properties.energy.program_type = attic_program_type

    constr_set = ConstructionSet('Attic Construction Set')
    polyiso = EnergyMaterial('PolyIso', 0.2, 0.03, 43, 1210, 'MediumRough')
    roof_constr = OpaqueConstruction('Attic Roof Construction',
                                     [roof_membrane, polyiso, wood])
    floor_constr = OpaqueConstruction('Attic Floor Construction',
                                      [wood, insulation, wood])
    constr_set.floor_set.interior_construction = floor_constr
    constr_set.roof_ceiling_set.exterior_construction = roof_constr
    building.unique_room_2ds[-1].properties.energy.construction_set = constr_set
    building.unique_room_2ds[-2].properties.energy.construction_set = constr_set

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])
    bright_leaves = ShadeConstruction('Bright Light Leaves', 0.5, 0.5, True)
    tree_canopy.properties.energy.construction = bright_leaves
    tree_trans = ScheduleRuleset.from_constant_value(
        'Tree Transmittance', 0.5, schedule_types.fractional)
    tree_canopy.properties.energy.transmittance_schedule = tree_trans

    model = Model('NewDevelopment', [building, building_big], [tree_canopy])

    hb_models = model.to_honeybee('Building', 10, False, tolerance=0.01)
    assert len(hb_models) == 2

    assert polyiso in hb_models[0].properties.energy.materials
    assert roof_constr in hb_models[0].properties.energy.constructions
    assert floor_constr in hb_models[0].properties.energy.constructions
    assert constr_set in hb_models[0].properties.energy.construction_sets
    assert hb_models[0].rooms[-1].properties.energy.construction_set == constr_set

    assert polyiso not in hb_models[1].properties.energy.materials
    assert roof_constr not in hb_models[1].properties.energy.constructions
    assert floor_constr not in hb_models[1].properties.energy.constructions
    assert constr_set not in hb_models[1].properties.energy.construction_sets

    assert schedule in hb_models[0].properties.energy.schedules
    assert attic_program_type in hb_models[0].properties.energy.program_types
    assert hb_models[0].rooms[-1].properties.energy.program_type == attic_program_type

    assert schedule not in hb_models[1].properties.energy.schedules
    assert attic_program_type not in hb_models[1].properties.energy.program_types

    assert bright_leaves in hb_models[0].properties.energy.constructions
    assert tree_trans in hb_models[0].properties.energy.schedules
    assert hb_models[0].orphaned_shades[-1].properties.energy.construction == bright_leaves
    assert hb_models[0].orphaned_shades[-1].properties.energy.transmittance_schedule == tree_trans

    assert bright_leaves not in hb_models[-1].properties.energy.constructions
    assert tree_trans not in hb_models[-1].properties.energy.schedules


def test_to_honeybee_construction_resolution():
    """Test the to_honeybee method with construction sets that conflict interiors."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    building.separate_top_bottom_floors()
    for room in story.room_2ds:
        room.properties.energy.program_type = office_program
        room.properties.energy.add_default_ideal_air()
    model = Model('NewDevelopment', [building])

    hb_model = model.to_honeybee('Building', 10, False, solve_ceiling_adjacencies=True)[0]
    assert hb_model.check_all(False) == ''

    constr_set = ConstructionSet('Attic Construction Set')
    polyiso = EnergyMaterial('PolyIso', 0.2, 0.03, 43, 1210, 'MediumRough')
    roof_constr = OpaqueConstruction('Attic Roof Construction',
                                     [roof_membrane, polyiso, wood])
    floor_constr = OpaqueConstruction('Attic Floor Construction',
                                      [wood, insulation, wood])
    constr_set.floor_set.interior_construction = floor_constr
    constr_set.roof_ceiling_set.exterior_construction = roof_constr
    building.unique_room_2ds[-1].properties.energy.construction_set = constr_set
    building.unique_room_2ds[-2].properties.energy.construction_set = constr_set

    hb_model = model.to_honeybee('Building', 10, False, solve_ceiling_adjacencies=True)[0]
    assert hb_model.check_all(False) == ''
    attics = [hb_model.rooms[-2], hb_model.rooms[-1]]
    sub_attics = [hb_model.rooms[-4], hb_model.rooms[-3]]
    for attic in attics:
        for floor in attic.floors:
            assert floor.properties.energy.construction == floor_constr
    for sub_attic in sub_attics:
        for ceiling in sub_attic.roof_ceilings:
            assert ceiling.properties.energy.construction == floor_constr


def test_to_urbanopt():
    """Test the Model.to.urbanopt method."""
    pts_1 = (Point3D(50, 50, 3), Point3D(60, 50, 3), Point3D(60, 60, 3), Point3D(50, 60, 3))
    pts_2 = (Point3D(60, 50, 3), Point3D(70, 50, 3), Point3D(70, 60, 3), Point3D(60, 60, 3))
    pts_3 = (Point3D(50, 70, 3), Point3D(70, 70, 3), Point3D(70, 80, 3), Point3D(50, 80, 3))
    room2d_1 = Room2D('Residence1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Residence2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Retail', Face3D(pts_3), 3)
    story_big = Story('RetailFloor', [room2d_3])
    story = Story('ResidenceFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 3
    building = Building('ResidenceBuilding', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 1
    building_big = Building('RetailBuildingBig', [story_big])

    pts_1 = (Point3D(0, 0, 3), Point3D(0, 5, 3), Point3D(15, 5, 3), Point3D(15, 0, 3))
    pts_2 = (Point3D(15, 0, 3), Point3D(15, 15, 3), Point3D(20, 15, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 5, 3), Point3D(0, 20, 3), Point3D(5, 20, 3), Point3D(5, 5, 3))
    pts_4 = (Point3D(5, 15, 3), Point3D(5, 20, 3), Point3D(20, 20, 3), Point3D(20, 15, 3))
    pts_5 = (Point3D(-5, -5, 3), Point3D(-10, -5, 3), Point3D(-10, -10, 3), Point3D(-5, -10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    room2d_5 = Room2D('Office5', Face3D(pts_5), 3)
    int_rms = Room2D.intersect_adjacency(
        [room2d_1, room2d_2, room2d_3, room2d_4, room2d_5], 0.01)
    story = Story('OfficeFloor', int_rms)
    story.rotate_xy(5, Point3D(0, 0, 0))
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 5
    building_mult = Building('OfficeBuilding', [story])

    # set program type
    building.properties.energy.set_all_room_2d_program_type(office_program)
    building_big.properties.energy.set_all_room_2d_program_type(office_program)
    building_mult.properties.energy.set_all_room_2d_program_type(office_program)

    # get context shade
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    # create the Model object
    model = Model('TestGeoJSON', [building, building_big, building_mult], [tree_canopy])

    # create the urbanopt folder
    location = Location('Boston', 'MA', 'USA', 42.366151, -71.019357)
    sim_folder = './tests/urbanopt_model'
    geojson, hb_model_jsons, hb_models = \
        model.to.urbanopt(model, location, folder=sim_folder)

    # check that the appropriate files were generated
    assert os.path.isfile(geojson)
    for model_json in hb_model_jsons:
        assert os.path.isfile(model_json)
    for h_model in hb_models:
        assert isinstance(h_model, hb_model.Model)

    # clean up the files
    nukedir(sim_folder, True)


def test_to_urbanopt_electric_network():
    """Test the Model.to.urbanopt method with an ElectricNetwork."""
    model_json = './tests/json/buffalo_test_district.dfjson'
    with open(model_json) as json_file:
        data = json.load(json_file)
    model = Model.from_dict(data)

    network_json = './tests/json/buffalo_electric_grid.json'
    with open(network_json) as json_file:
        data = json.load(json_file)
    network = ElectricalNetwork.from_dict(data)

    # create the urbanopt folder
    location = Location('Buffalo', 'NY', 'USA', 42.813153, -78.852466)
    sim_folder = './tests/urbanopt_model_buffalo'
    geojson, hb_model_jsons, hb_models = \
        model.to.urbanopt(model, location, electrical_network=network, folder=sim_folder)

    # check that the appropriate files were generated
    assert os.path.isfile(geojson)
    for model_json in hb_model_jsons:
        assert os.path.isfile(model_json)
    for h_model in hb_models:
        assert isinstance(h_model, hb_model.Model)
    assert os.path.isfile(os.path.join(sim_folder, 'electrical_database.json'))

    # clean up the files
    nukedir(sim_folder, True)


def test_to_urbanopt_des_loop():
    """Test the Model.to.urbanopt method with an GHEThermalLoop."""
    model_json = './tests/json/buffalo_test_district.dfjson'
    with open(model_json) as json_file:
        data = json.load(json_file)
    model = Model.from_dict(data)

    loop_json = './tests/json/buffalo_ghe_des.json'
    with open(loop_json) as json_file:
        data = json.load(json_file)
    des_loop = GHEThermalLoop.from_dict(data)

    # create the urbanopt folder
    location = Location('Buffalo', 'NY', 'USA', 42.813153, -78.852466)
    sim_folder = './tests/urbanopt_model_buffalo_ghe'
    geojson, hb_model_jsons, hb_models = \
        model.to.urbanopt(model, location, des_loop=des_loop, folder=sim_folder)

    # check that the appropriate files were generated
    assert os.path.isfile(geojson)
    for model_json in hb_model_jsons:
        assert os.path.isfile(model_json)
    for h_model in hb_models:
        assert isinstance(h_model, hb_model.Model)
    assert os.path.isfile(os.path.join(sim_folder, 'system_params.json'))

    # clean up the files
    nukedir(sim_folder, True)
