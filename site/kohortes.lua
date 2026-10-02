-- Shortcodes that read the data product through src/cli.js (ADR 0005: the gateway for
-- values). A missing or unprovenanced value makes node exit non-zero, pandoc.pipe raises,
-- and the render fails.
--   {{< fact population EL 2024 >}}            optional sex and age after the period
--   {{< chart figures/fertility.json >}}
local cli = quarto.utils.resolve_path("src/cli.js")

local function run(command, args)
  local argv = { cli, command }
  for _, a in ipairs(args) do
    argv[#argv + 1] = pandoc.utils.stringify(a)
  end
  return pandoc.pipe("node", argv, "")
end

return {
  fact = function(args)
    return pandoc.RawInline("html", run("fact", args))
  end,
  chart = function(args)
    return pandoc.RawBlock("html", run("chart", args))
  end,
}
