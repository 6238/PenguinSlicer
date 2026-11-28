// A small stand-in for Orca's list of process settings, written by hand for the tests of
// scripts/make_settings_table.py. Not Orca's code.

static std::vector<std::string> s_Preset_print_options{
    "layer_height", "wall_loops",
    "infill_density",
    "first_line_width",
    // "retired_setting",
    "infill_pattern", "support_on", /*"also_retired",*/
    "solid_pattern", "wall_order",
    "outer_speed",
    "template_text",
    "ironing_inset",
    "end_gcode",
    "extruder_slots",
    "variant_speed",
    "inherits",
};

static std::vector<std::string> s_Preset_filament_options {
    "bed_temperature"
};
