local wezterm = require("wezterm")

local M = {}

-- Light palette (GitHub Light, from terminalcolors.com)
M.light = {
	colors = {
		foreground = "#1F2328",
		background = "#F6F8FA",
		cursor_bg = "#FB8500",
		cursor_fg = "#F6F8FA",
		cursor_border = "#FB8500",
		selection_bg = "#B6E3FF",
		selection_fg = "#1F2328",
		scrollbar_thumb = "#D0D7DE",
		split = "#0969DA",
		ansi = {
			"#24292F", "#CF222E", "#116329", "#4D2D00",
			"#0969DA", "#8250DF", "#1B7C83", "#6E7781",
		},
		brights = {
			"#57606A", "#A40E26", "#1A7F37", "#633C01",
			"#218BFF", "#A475F9", "#3192AA", "#8C959F",
		},
		tab_bar = {
			background = "#EAEEF2",
			inactive_tab_edge = "#D1D9E0",
			active_tab = { bg_color = "#0969DA", fg_color = "#FFFFFF" },
			inactive_tab = { bg_color = "#D0D7DE", fg_color = "#57606A" },
			inactive_tab_hover = { bg_color = "#D8DEE4", fg_color = "#1F2328", italic = true },
			new_tab = { bg_color = "#D0D7DE", fg_color = "#57606A" },
			new_tab_hover = { bg_color = "#0969DA", fg_color = "#FFFFFF", italic = true },
		},
	},
	command_palette = { bg = "#0969DA", fg = "#FFFFFF" },
	status = {
		bg = "#F6F8FA",
		bar_bg = "#EAEEF2",
		fg = "#1F2328",
		active = "#0969DA",
		active_fg = "#FFFFFF",
		inactive = "#D0D7DE",
		hover = "#D8DEE4",
		dark = "#1F2328",
	},
	sb_colors = { "#D0D7DE", "#D8DEE4", "#E1E4E8", "#EAEEF2" },
	search_bg = "#BF8700",
	copy_bg = "#1A7F37",
	git_bg = "#8250DF",
}

-- Dark palette (Deus, from terminalcolors.com)
M.dark = {
	colors = {
		foreground = "#EAEAEA",
		background = "#2C323B",
		cursor_bg = "#FABD2F",
		cursor_fg = "#2C323B",
		cursor_border = "#FABD2F",
		selection_bg = "#EAEAEA",
		selection_fg = "#2C323B",
		scrollbar_thumb = "#3A414A",
		split = "#83A598",
		ansi = {
			"#242A32", "#D54E53", "#98C379", "#E5C07B",
			"#83A598", "#C678DD", "#70C0BA", "#EAEAEA",
		},
		brights = {
			"#8A8A8A", "#EC3E45", "#90C966", "#EDBF69",
			"#73BA9F", "#C858E9", "#2BCEC2", "#FFFFFF",
		},
		tab_bar = {
			background = "#242A32",
			inactive_tab_edge = "#3A414A",
			active_tab = { bg_color = "#83A598", fg_color = "#2C323B" },
			inactive_tab = { bg_color = "#3A414A", fg_color = "#EAEAEA" },
			inactive_tab_hover = { bg_color = "#2F3540", fg_color = "#EAEAEA", italic = true },
			new_tab = { bg_color = "#3A414A", fg_color = "#EAEAEA" },
			new_tab_hover = { bg_color = "#83A598", fg_color = "#2C323B", italic = true },
		},
	},
	command_palette = { bg = "#83A598", fg = "#2C323B" },
	status = {
		bg = "#2C323B",
		bar_bg = "#242A32",
		fg = "#EAEAEA",
		active = "#83A598",
		active_fg = "#2C323B",
		inactive = "#3A414A",
		hover = "#2F3540",
		dark = "#2C323B",
	},
	sb_colors = { "#4A4F58", "#565C66", "#626874", "#6E7582" },
	search_bg = "#E5C07B",
	copy_bg = "#98C379",
	git_bg = "#C678DD",
}

function M.mode_for_appearance(appearance)
	if appearance and appearance:find("Dark") then
		return "dark"
	end
	return "light"
end

-- Effective mode: manual override wins, else macOS appearance.
function M.current_mode()
	if wezterm.GLOBAL.theme_override then
		return wezterm.GLOBAL.theme_override
	end
	return M.mode_for_appearance(wezterm.gui.get_appearance())
end

function M.current()
	return M[M.current_mode()]
end

-- Flip override to the opposite of the current effective mode.
function M.toggle()
	local current = M.current_mode()
	wezterm.GLOBAL.theme_override = (current == "light") and "dark" or "light"
end

-- Drop manual override so appearance follows macOS again.
function M.clear_override()
	wezterm.GLOBAL.theme_override = nil
end

return M
