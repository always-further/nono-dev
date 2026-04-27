local wezterm = require("wezterm")
local theme = require("theme")
local config = {}

if wezterm.config_builder then
	config = wezterm.config_builder()
end

config.default_cursor_style = "BlinkingUnderline"
config.cursor_thickness = 3
config.force_reverse_video_cursor = false
config.cursor_blink_rate = 500
config.cursor_blink_ease_in = "EaseIn"
config.cursor_blink_ease_out = "EaseOut"

config.automatically_reload_config = true
config.window_close_confirmation = "NeverPrompt"
config.adjust_window_size_when_changing_font_size = false
config.window_decorations = "RESIZE"
config.check_for_updates = false
config.use_fancy_tab_bar = false
config.tab_bar_at_bottom = true
config.font_size = 14
config.font = wezterm.font("FiraCode Nerd Font", { weight = "Regular" })
config.enable_tab_bar = true
config.hide_tab_bar_if_only_one_tab = false
config.tab_max_width = 32
config.bold_brightens_ansi_colors = "BrightAndBold"
config.allow_square_glyphs_to_overflow_width = "WhenFollowedBySpace"
config.anti_alias_custom_block_glyphs = true
config.warn_about_missing_glyphs = false
config.window_padding = {
	left = 2,
	right = 2,
	top = 2,
	bottom = 1,
}
config.window_background_opacity = 0.98
config.macos_window_background_blur = 20
config.enable_scroll_bar = true
config.inactive_pane_hsb = {
	saturation = 0.8,
	brightness = 0.9,
}
config.pane_focus_follows_mouse = true

-- Initial colors based on macOS appearance at startup; events.lua keeps it in sync.
local initial = theme.current()
config.colors = initial.colors
config.command_palette_bg_color = initial.command_palette.bg
config.command_palette_fg_color = initial.command_palette.fg
config.command_palette_font_size = 14
local act = wezterm.action

local function notify(window, message, status_message, ok)
	wezterm.GLOBAL.clipboard_status = {
		message = status_message,
		ok = ok,
		expires_at = os.time() + 2,
	}
	pcall(function()
		window:toast_notification("WezTerm", message, nil, 1800)
	end)
end

local function copy_selected_text(window, pane)
	local ok, selection = pcall(function()
		return window:get_selection_text_for_pane(pane)
	end)

	if ok and (selection == nil or selection == "") then
		notify(window, "No selection to copy", "NO SELECTION", false)
		return false
	end

	window:perform_action(act.CopyTo("Clipboard"), pane)
	notify(window, "Copied selection to clipboard", "COPIED", true)
	return true
end

local copy_selection = wezterm.action_callback(function(window, pane)
	copy_selected_text(window, pane)
end)

local copy_selection_and_close = wezterm.action_callback(function(window, pane)
	if copy_selected_text(window, pane) then
		window:perform_action(act.CopyMode("Close"), pane)
	end
end)

config.keys = {
	{ key = "Enter", mods = "CTRL", action = act({ SendString = "\x1b[13;5u" }) },
	{ key = "Enter", mods = "SHIFT", action = act({ SendString = "\x1b[13;2u" }) },
	{ key = "c", mods = "CMD", action = copy_selection },
	{ key = "c", mods = "CTRL|SHIFT", action = copy_selection },
	{ key = "d", mods = "CMD", action = act({ SplitHorizontal = { domain = "CurrentPaneDomain" } }) },
	{ key = "d", mods = "CMD|SHIFT", action = act({ SplitVertical = { domain = "CurrentPaneDomain" } }) },
	{ key = "LeftArrow", mods = "CMD|SHIFT", action = act({ ActivatePaneDirection = "Left" }) },
	{ key = "RightArrow", mods = "CMD|SHIFT", action = act({ ActivatePaneDirection = "Right" }) },
	{ key = "UpArrow", mods = "CMD|SHIFT", action = act({ ActivatePaneDirection = "Up" }) },
	{ key = "DownArrow", mods = "CMD|SHIFT", action = act({ ActivatePaneDirection = "Down" }) },
	{ key = "w", mods = "CMD", action = act({ CloseCurrentPane = { confirm = false } }) },
	{ key = "z", mods = "CMD|SHIFT", action = act.TogglePaneZoomState },
	-- Option+Arrow: move by word
	{ key = "LeftArrow", mods = "OPT", action = act({ SendString = "\x1bb" }) },
	{ key = "RightArrow", mods = "OPT", action = act({ SendString = "\x1bf" }) },
	-- Cmd+Arrow: move to beginning/end of line
	{ key = "LeftArrow", mods = "CMD", action = act({ SendString = "\x01" }) },
	{ key = "RightArrow", mods = "CMD", action = act({ SendString = "\x05" }) },
	-- Cmd+Shift+T: toggle light/dark theme (sets manual override)
	{
		key = "t",
		mods = "CMD|SHIFT",
		action = wezterm.action_callback(function(window)
			theme.toggle()
			local m = theme.current()
			local overrides = window:get_config_overrides() or {}
			overrides.colors = m.colors
			overrides.command_palette_bg_color = m.command_palette.bg
			overrides.command_palette_fg_color = m.command_palette.fg
			window:set_config_overrides(overrides)
		end),
	},
	-- Cmd+Shift+Y: clear manual override, follow macOS appearance
	{
		key = "y",
		mods = "CMD|SHIFT",
		action = wezterm.action_callback(function(window)
			theme.clear_override()
			local m = theme.current()
			local overrides = window:get_config_overrides() or {}
			overrides.colors = m.colors
			overrides.command_palette_bg_color = m.command_palette.bg
			overrides.command_palette_fg_color = m.command_palette.fg
			window:set_config_overrides(overrides)
		end),
	},
}

local key_tables = wezterm.gui.default_key_tables()
local copy_mode_overrides = {
	{ key = "y", mods = "NONE", action = copy_selection_and_close },
	{ key = "Enter", mods = "NONE", action = copy_selection_and_close },
	{ key = "c", mods = "CMD", action = copy_selection_and_close },
	{ key = "c", mods = "CTRL", action = copy_selection_and_close },
	{ key = "c", mods = "CTRL|SHIFT", action = copy_selection_and_close },
}
local overridden_copy_keys = {}
for _, binding in ipairs(copy_mode_overrides) do
	overridden_copy_keys[binding.key .. ":" .. binding.mods] = true
end
local copy_mode = {}
for _, binding in ipairs(key_tables.copy_mode) do
	if not overridden_copy_keys[binding.key .. ":" .. binding.mods] then
		table.insert(copy_mode, binding)
	end
end
for _, binding in ipairs(copy_mode_overrides) do
	table.insert(copy_mode, binding)
end
key_tables.copy_mode = copy_mode
config.key_tables = key_tables

config.hyperlink_rules = {
	{
		regex = "\\((\\w+://\\S+)\\)",
		format = "$1",
		highlight = 1,
	},
	{
		regex = "\\[(\\w+://\\S+)\\]",
		format = "$1",
		highlight = 1,
	},
	{
		regex = "\\{(\\w+://\\S+)\\}",
		format = "$1",
		highlight = 1,
	},
	{
		regex = "<(\\w+://\\S+)>",
		format = "$1",
		highlight = 1,
	},
	{
		regex = "[^(]\\b(\\w+://\\S+[)/a-zA-Z0-9-]+)",
		format = "$1",
		highlight = 1,
	},
}
return config
