// A small stand-in for Orca's option definitions, written by hand for the tests of
// scripts/make_settings_table.py in the form Orca's own file takes. Not Orca's code.

static t_config_enum_values s_keys_map_Pattern {
    { "lines", ptLines },
    { "grid", ptGrid },
    { "hidden", ptHidden },
    { "honeycomb", ptHoneycomb }
};
CONFIG_OPTION_ENUM_DEFINE_STATIC_MAPS(Pattern)

static t_config_enum_values s_keys_map_WallOrder = {
    { "inner_outer", woInnerOuter },
    { "outer_inner", int(WallOrder::woOuterInner) },
};
CONFIG_OPTION_ENUM_DEFINE_STATIC_MAPS(WallOrder)

void PrintConfigDef::init_fff_params()
{
    ConfigOptionDef* def;
    const int max_speed = 1000;

    def = this->add("layer_height", coFloat);
    def->label = L("Layer height");
    def->category = L("Quality");
    def->tooltip = L("How tall each layer is. "
                     "Smaller is finer.");
    def->sidetext = L("mm");	// millimetres
    def->min = 0;
    def->set_default_value(new ConfigOptionFloat(0.2));

    def = this->add("wall_loops", coInt);
    def->label = L("Wall loops");
    def->tooltip = L("Number of walls.");
    def->min = 0;
    def->max = 1000;
    def->set_default_value(new ConfigOptionInt(2));

    def = this->add("infill_density", coPercent);
    def->label = L("Infill density");
    // xgettext:no-c-format
    def->tooltip = L("Density of the \"sparse\" infill, 100% is solid.");
    def->sidetext = "%";
    def->min = 0;
    def->max = 100;
    def->set_default_value(new ConfigOptionPercent(15));

    def = this->add("first_line_width", coFloatOrPercent);
    def->label = L("First layer");
    def->tooltip = L("Line width of the first layer. If expressed as a %, it will be computed over the nozzle diameter.");
    def->sidetext = L("mm or %");
    def->min = 0;
    def->max_literal = 10;
    def->set_default_value(new ConfigOptionFloatOrPercent(0., false));

    auto def_pattern = def = this->add("infill_pattern", coEnum);
    def->label = L("Infill pattern");
    def->tooltip = L("Line pattern of the infill.");
    def->enum_keys_map = &ConfigOptionEnum<Pattern>::get_enum_values();
    def->enum_values.push_back("lines");
    def->enum_values.push_back("grid");
    def->enum_values.emplace_back("honeycomb");
    def->enum_labels.push_back(L("Lines"));
    def->enum_labels.push_back(L("Grid"));
    def->enum_labels.emplace_back(L("Honeycomb"));
    def->set_default_value(new ConfigOptionEnum<Pattern>(Pattern::ptGrid));

    def = this->add("solid_pattern", coEnum);
    def->label = L("Solid pattern");
    def->tooltip = def_pattern->tooltip;
    def->enum_keys_map = &ConfigOptionEnum<Pattern>::get_enum_values();
    def->enum_values = def_pattern->enum_values;
    def->enum_labels = def_pattern->enum_labels;
    def->set_default_value(new ConfigOptionEnum<Pattern>(ptLines));

    def = this->add("wall_order", coEnum);
    def->label = L("Wall order");
    def->tooltip = L("Which wall comes first.");
    def->enum_values = {"inner_outer", "outer_inner"};
    def->enum_labels = {L("Inner, then outer"), L("Outer, then inner")};
    def->set_default_value(new ConfigOptionEnum<WallOrder>(woInnerOuter));

    def = this->add("support_on", coBool);
    def->label = L("Enable support");
    def->tooltip = L("Enable support generation.");
    def->set_default_value(new ConfigOptionBool(false));

    def = this->add("outer_speed", coFloat);
    def->full_label = L("Outer wall speed");
    def->label = L("Outer wall");
    def->tooltip = L("Speed of the outer wall.");
    def->sidetext = L("mm/s");
    def->min = -max_speed;
    def->max = max_speed;
    def->set_default_value(new ConfigOptionFloat(60));

    def = this->add("template_text", coString);
    def->label = L("Rotation template");
    def->set_default_value(new ConfigOptionString(""));

    def = this->add("ironing_inset", coFloat);
    def->label = L("Ironing inset");
    def->tooltip = L("Distance from the edges.");
    def->set_default_value(new ConfigOptionFloat(0));

    def = this->add("end_gcode", coString);
    def->label = L("End G-code");
    def->tooltip = L("G-code at the end.");
    def->set_default_value(new ConfigOptionString("M400"));

    def = this->add("extruder_slots", coInts);
    def->label = L("Extruder slots");
    def->set_default_value(new ConfigOptionInts{ 1 });

    def = this->add_nullable("variant_speed", coFloats);
    def->label = L("Variant speed");
    def->tooltip = L("One speed for each extruder variant.");
    def->sidetext = L("mm/s");
    def->min = 0;
    def->set_default_value(new ConfigOptionFloatsNullable{ 30 });

    for (const char *opt_key : { "loop_a", "loop_b" }) {
        def = this->add(opt_key, coFloat);
        def->label = L("Made in a loop");
    }

    def = this->add("bed_temperature", coInts);
    def->label = L("Bed temperature");
    def->max = bed_limit(); // not read, and not needed: no process setting
    def->set_default_value(new ConfigOptionInts{ 60 });
}

std::set<std::string> print_options_with_variant = {
    //"outer_speed",
    "variant_speed",
    "extruder_slots"
};
