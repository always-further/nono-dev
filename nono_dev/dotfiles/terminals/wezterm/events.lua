local wezterm = require("wezterm")
local theme_module = require("theme")
local mux = wezterm.mux
local nf = wezterm.nerdfonts

-- Tab separators (powerline arrow style)
local TAB_LEFT = nf.pl_right_hard_divider
local TAB_RIGHT = nf.pl_left_hard_divider

-- Status bar separators (powerline style)
local SB_LEFT = nf.pl_left_hard_divider
local SB_RIGHT = nf.pl_right_hard_divider

wezterm.on("gui-startup", function()
	mux.spawn_window({})
end)

wezterm.on("update-status", function(window, pane)
	local palette = theme_module.current()
	local theme = palette.status
	local sb_colors = palette.sb_colors

	-- Left status: mode indicator
	local mode = window:active_key_table()
	local mode_label = ""
	local mode_bg = theme.active
	local clipboard_status = wezterm.GLOBAL.clipboard_status
	if clipboard_status and clipboard_status.expires_at and clipboard_status.expires_at >= os.time() then
		mode_label = " " .. nf.md_content_copy .. " " .. clipboard_status.message .. " "
		mode_bg = clipboard_status.ok and palette.copy_bg or palette.search_bg
	elseif clipboard_status and clipboard_status.expires_at and clipboard_status.expires_at < os.time() then
		wezterm.GLOBAL.clipboard_status = nil
	end

	if mode_label == "" and mode == "search_mode" then
		mode_label = " " .. nf.md_magnify .. " SEARCH "
		mode_bg = palette.search_bg
	elseif mode_label == "" and mode == "copy_mode" then
		mode_label = " " .. nf.md_content_copy .. " COPY "
		mode_bg = palette.copy_bg
	end

	if mode_label ~= "" then
		window:set_left_status(wezterm.format({
			{ Background = { Color = mode_bg } },
			{ Foreground = { Color = theme.active_fg } },
			{ Attribute = { Intensity = "Bold" } },
			{ Text = mode_label },
			{ Background = { Color = theme.bar_bg } },
			{ Foreground = { Color = mode_bg } },
			{ Text = SB_LEFT },
		}))
	else
		window:set_left_status("")
	end

	-- Right status: cwd, git branch, time
	local cwd_uri = pane:get_current_working_dir()
	local cwd = ""
	local branch = ""

	if cwd_uri then
		cwd = cwd_uri.file_path or ""
		local home = os.getenv("HOME") or ""
		if home ~= "" and cwd:sub(1, #home) == home then
			cwd = "~" .. cwd:sub(#home + 1)
		end
		-- Shorten to last 2 path components if long
		local parts = {}
		for part in cwd:gmatch("[^/]+") do
			table.insert(parts, part)
		end
		if #parts > 2 then
			if parts[1] == "~" then
				cwd = "~/" .. parts[#parts - 1] .. "/" .. parts[#parts]
			else
				cwd = parts[#parts - 1] .. "/" .. parts[#parts]
			end
		end

		local success, stdout = wezterm.run_child_process({
			"git", "-C", cwd_uri.file_path or "", "rev-parse", "--abbrev-ref", "HEAD",
		})
		if success and stdout then
			branch = stdout:gsub("%s+$", "")
		end
	end

	local time = wezterm.strftime("%a %b %-d  %H:%M")
	local hostname = wezterm.hostname()
	-- Shorten hostname
	hostname = hostname:gsub("%..*", "")

	local status = {}

	-- Build right status segments (right-to-left visually, but we build left-to-right)
	-- Segment 1: hostname (darkest)
	table.insert(status, { Background = { Color = theme.bar_bg } })
	table.insert(status, { Foreground = { Color = sb_colors[1] } })
	table.insert(status, { Text = SB_RIGHT })
	table.insert(status, { Background = { Color = sb_colors[1] } })
	table.insert(status, { Foreground = { Color = theme.dark } })
	table.insert(status, { Text = " " .. nf.md_laptop .. " " .. hostname .. " " })

	-- Segment 2: cwd (blue, matching active tab)
	if cwd ~= "" then
		table.insert(status, { Foreground = { Color = theme.active } })
		table.insert(status, { Text = SB_RIGHT })
		table.insert(status, { Background = { Color = theme.active } })
		table.insert(status, { Foreground = { Color = theme.active_fg } })
		table.insert(status, { Text = " " .. nf.md_folder .. " " .. cwd .. " " })
	end

	-- Segment 2b: git branch (theme accent)
	if branch ~= "" then
		table.insert(status, { Foreground = { Color = palette.git_bg } })
		table.insert(status, { Text = SB_RIGHT })
		table.insert(status, { Background = { Color = palette.git_bg } })
		table.insert(status, { Foreground = { Color = theme.active_fg } })
		table.insert(status, { Text = " " .. nf.dev_git_branch .. " " .. branch .. " " })
	end

	-- Segment 3: date/time
	table.insert(status, { Foreground = { Color = sb_colors[3] } })
	table.insert(status, { Text = SB_RIGHT })
	table.insert(status, { Background = { Color = sb_colors[3] } })
	table.insert(status, { Foreground = { Color = theme.dark } })
	table.insert(status, { Text = " " .. time .. " " })

	-- Segment 4: battery (lightest)
	local battery = wezterm.battery_info()
	if battery and #battery > 0 then
		local charge = battery[1].state_of_charge * 100
		local bat_icon = nf.md_battery
		if charge >= 90 then bat_icon = nf.md_battery
		elseif charge >= 70 then bat_icon = nf.md_battery_70
		elseif charge >= 50 then bat_icon = nf.md_battery_50
		elseif charge >= 30 then bat_icon = nf.md_battery_30
		elseif charge >= 10 then bat_icon = nf.md_battery_20
		else bat_icon = nf.md_battery_10
		end
		if battery[1].state == "Charging" then
			bat_icon = nf.md_battery_charging
		end
		table.insert(status, { Foreground = { Color = sb_colors[4] } })
		table.insert(status, { Text = SB_RIGHT })
		table.insert(status, { Background = { Color = sb_colors[4] } })
		table.insert(status, { Foreground = { Color = theme.dark } })
		table.insert(status, { Text = " " .. bat_icon .. " " .. string.format("%.0f%%", charge) .. " " })
	end

	window:set_right_status(wezterm.format(status))
end)

wezterm.on("format-tab-title", function(tab, tabs, panes, config, hover, max_width)
	local theme = theme_module.current().status

	local tab_num = tab.tab_index + 1
	local title = tab.active_pane.title
	if title and #title > 20 then
		title = title:sub(1, 20) .. ".."
	end

	local is_active = tab.is_active
	local tab_bg
	if is_active then
		tab_bg = theme.active
	elseif hover then
		tab_bg = theme.hover
	else
		tab_bg = theme.inactive
	end

	local tab_fg
	if is_active then
		tab_fg = theme.active_fg
	elseif hover then
		tab_fg = theme.dark
	else
		tab_fg = theme.dark
	end

	return {
		-- Colored number segment
		{ Background = { Color = tab_bg } },
		{ Foreground = { Color = tab_fg } },
		{ Attribute = { Intensity = is_active and "Bold" or "Normal" } },
		{ Text = " " .. tostring(tab_num) .. " " },
		-- Arrow pointing right (tab color into bar bg)
		{ Background = { Color = theme.bar_bg } },
		{ Foreground = { Color = tab_bg } },
		{ Text = nf.pl_left_hard_divider },
		-- Tab title on bar background
		{ Foreground = { Color = is_active and theme.fg or (hover and theme.fg or "#908e82") } },
		{ Text = " " .. title .. " " },
	}
end)

-- Keep colors in sync when macOS appearance flips (or any config reload).
-- Detects change via background color; no-op if already applied.
wezterm.on("window-config-reloaded", function(window)
	local m = theme_module.current()
	local overrides = window:get_config_overrides() or {}
	if overrides.colors and overrides.colors.background == m.colors.background then
		return
	end
	overrides.colors = m.colors
	overrides.command_palette_bg_color = m.command_palette.bg
	overrides.command_palette_fg_color = m.command_palette.fg
	window:set_config_overrides(overrides)
end)
