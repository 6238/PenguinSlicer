// A small stand-in for Orca's pages of process settings, written by hand for the tests of
// scripts/make_settings_table.py. Not Orca's code.

void TabPrint::build()
{
    auto page = add_options_page(L("Quality"), "custom-gcode_quality");
        auto optgroup = page->new_optgroup(L("Layer height"), L"param_layer_height");
        optgroup->append_single_option_line("layer_height", "quality_settings_layer_height");
        optgroup = page->new_optgroup(L("Line width"), L"param_line_width");
        optgroup->append_single_option_line("first_line_width");
        optgroup = page->new_optgroup(L("Ironing"), L"param_ironing");
        // optgroup->append_single_option_line("ironing_inset");

    page = add_options_page(L("Strength"), "custom-gcode_strength");
        optgroup = page->new_optgroup(L("Walls"), L"param_wall");
        optgroup->append_single_option_line("wall_loops", "strength_settings_walls#wall-loops");
        optgroup->append_single_option_line("wall_order");
        optgroup = page->new_optgroup(L("Infill"), L"param_infill");
        optgroup->append_single_option_line("infill_pattern");
        optgroup->append_single_option_line("infill_density");
        optgroup->append_single_option_line("template_text");
        optgroup->append_single_option_line("solid_pattern");

    page = add_options_page(L("Speed"), "custom-gcode_speed");
        optgroup = page->new_optgroup(L("Other layers speed"), L"param_speed", 15);
        Line line = { L("Walls"), L("Speeds of the walls") };
        line.append_option(optgroup->get_option("outer_speed"));
        line.append_option(optgroup->get_option("variant_speed"));
        optgroup->append_line(line);

    page = add_options_page(L("Support"), "custom-gcode_support");
        optgroup = page->new_optgroup(L("Support"), L"param_support");
        optgroup->append_single_option_line("support_on", "support_settings_support");

    page = add_options_page(L("Others"), "custom-gcode_other");
        optgroup = page->new_optgroup(L("End G-code"), L"param_gcode", 0);
        Option option = optgroup->get_option("end_gcode");
        option.opt.full_width = true;
        optgroup->append_single_option_line(option);
}

void TabPrint::reload_config()
{
}

void TabFilament::build()
{
    auto page = add_options_page(L("Filament"), "custom-gcode_filament");
        auto optgroup = page->new_optgroup(L("Temperature"), L"param_temperature");
        optgroup->append_single_option_line("bed_temperature");
}
