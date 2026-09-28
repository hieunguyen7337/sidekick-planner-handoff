-- latex_prep.lua — LaTeX-only fixes for arXiv build

local log_path = os.getenv("STRIP_LOG")
if not log_path or log_path == "" then
  log_path = "strip_internal.log"
end

local paper_dir = os.getenv("PAPER_DIR") or ""

-- \needlines guard: tables estimated at <= NEEDLINES_MAX lines are kept whole; longer
-- ones get a guard of NEEDLINES_SPLIT lines (caption + header + about three rows).
local needlines_max = tonumber(os.getenv("NEEDLINES_MAX") or "") or 12
local needlines_split = tonumber(os.getenv("NEEDLINES_SPLIT") or "") or 8

local function log_info(msg)
  local f = io.open(log_path, "a")
  if f then
    f:write(string.format("INFO\t%s\n", msg))
    f:close()
  end
end

local function file_exists(path)
  local f = io.open(path, "r")
  if f then
    f:close()
    return true
  end
  return false
end

-- LaTeX code escaping
local function latex_escape_code(s, in_header)
  local out = {}
  local len = #s
  local i = 1
  while i <= len do
    local c = s:sub(i, i)
    if c == "\\" then
      table.insert(out, "\\textbackslash{}")
    elseif c == "{" then
      if in_header then
        table.insert(out, "\\{")
      else
        table.insert(out, "\\{\\allowbreak{}")
      end
    elseif c == "}" then
      table.insert(out, "\\}")
    elseif c == "$" then
      table.insert(out, "\\$")
    elseif c == "&" then
      table.insert(out, "\\&")
    elseif c == "#" then
      table.insert(out, "\\#")
    elseif c == "^" then
      table.insert(out, "\\^{}")
    elseif c == "_" then
      if in_header then
        table.insert(out, "\\_")
      else
        table.insert(out, "\\_\\allowbreak{}")
      end
    elseif c == "%" then
      table.insert(out, "\\%")
    elseif c == "~" then
      table.insert(out, "\\textasciitilde{}")
    elseif not in_header and (c == "/" or c == "." or c == ",") then
      table.insert(out, c .. "\\allowbreak{}")
    else
      table.insert(out, c)
    end
    i = i + 1
  end
  return table.concat(out)
end

-- Table caption formatting: make leading "Table <label>:" bold
local function format_table_caption_inlines(inlines)
  if not inlines or #inlines == 0 then return inlines end
  local full_text = pandoc.utils.stringify(inlines)
  local label = full_text:match("^(Table%s+[A-Z]*%d+[a-z]?:)")
  if not label then return inlines end
  
  if #inlines >= 3 and inlines[1].t == "Str" and inlines[1].text == "Table" 
     and inlines[2].t == "Space" and inlines[3].t == "Str" and inlines[3].text:match("^[A-Z]*%d+[a-z]?:") then
    local label_inlines = { pandoc.Str("Table"), pandoc.Space(), pandoc.Str(inlines[3].text) }
    local res = { pandoc.Strong(label_inlines) }
    for k = 4, #inlines do
      table.insert(res, inlines[k])
    end
    return res
  elseif #inlines >= 1 and inlines[1].t == "Str" and inlines[1].text:match("^Table%s+[A-Z]*%d+[a-z]?:") then
    local res = { pandoc.Strong({ pandoc.Str(label) }) }
    local rem = inlines[1].text:sub(#label + 1)
    if rem ~= "" then table.insert(res, pandoc.Str(rem)) end
    for k = 2, #inlines do
      table.insert(res, inlines[k])
    end
    return res
  end
  return inlines
end

-- Figure caption formatting: make leading "Figure <n>." bold
local function format_figure_caption(fig)
  if fig.caption and fig.caption.long and #fig.caption.long > 0 then
    local first_blk = fig.caption.long[1]
    if first_blk.content and #first_blk.content >= 1 then
      local inlines = first_blk.content
      local full_text = pandoc.utils.stringify(inlines)
      local label = full_text:match("^(Figure%s+[A-Z]*%d+[a-z]?[%.%:]?)")
      if label then
        if #inlines >= 3 and inlines[1].t == "Str" and inlines[1].text == "Figure"
           and inlines[2].t == "Space" and inlines[3].t == "Str" and inlines[3].text:match("^[A-Z]*%d+[a-z]?[%.%:]?") then
          local label_inlines = { pandoc.Str("Figure"), pandoc.Space(), pandoc.Str(inlines[3].text) }
          local res = { pandoc.Strong(label_inlines) }
          for k = 4, #inlines do
            table.insert(res, inlines[k])
          end
          first_blk.content = res
        elseif inlines[1].t == "Str" and inlines[1].text:match("^Figure%s+[A-Z]*%d+[a-z]?[%.%:]?") then
          local res = { pandoc.Strong({ pandoc.Str(label) }) }
          local rem = inlines[1].text:sub(#label + 1)
          if rem ~= "" then table.insert(res, pandoc.Str(rem)) end
          for k = 2, #inlines do
            table.insert(res, inlines[k])
          end
          first_blk.content = res
        end
      end
    end
  end
  return fig
end

-- Wide table column width recomputation
local function compute_table_widths(tbl)
  if not tbl.colspecs or #tbl.colspecs == 0 then return tbl end
  local num_cols = #tbl.colspecs
  
  local all_numeric = true
  for _, cs in ipairs(tbl.colspecs) do
    if type(cs[2]) ~= "number" or cs[2] <= 0 then
      all_numeric = false
      break
    end
  end
  if not all_numeric then return tbl end
  
  local max_len = {}
  local max_token_len = {}
  for c = 1, num_cols do
    max_len[c] = 0
    max_token_len[c] = 0
  end
  
  local function scan_rows(rows)
    if not rows then return end
    for _, r in ipairs(rows) do
      for c = 1, math.min(num_cols, #r.cells) do
        local cell_text = pandoc.utils.stringify(r.cells[c].contents)
        local l = utf8.len(cell_text) or #cell_text
        if l > max_len[c] then max_len[c] = l end
        for token in cell_text:gmatch("%S+") do
          local tl = utf8.len(token) or #token
          if tl > max_token_len[c] then max_token_len[c] = tl end
        end
      end
    end
  end
  
  scan_rows(tbl.head.rows)
  for _, b in ipairs(tbl.bodies) do
    scan_rows(b.head)
    scan_rows(b.body)
  end
  scan_rows(tbl.foot.rows)
  
  local L = {}
  local sum_L = 0
  for c = 1, num_cols do
    local base_l = math.max(6, math.min(70, max_len[c]))
    local token_floor = math.min(32, max_token_len[c] + 2)
    L[c] = math.max(base_l, token_floor)
    sum_L = sum_L + L[c]
  end
  
  local w = {}
  local sum_w = 0
  for c = 1, num_cols do
    local raw_w = L[c] / sum_L
    w[c] = math.max(0.08, raw_w)
    sum_w = sum_w + w[c]
  end
  
  for c = 1, num_cols do
    tbl.colspecs[c][2] = w[c] / sum_w
  end
  
  return tbl
end

-- Code block formatting & auto-sizing
local function format_codeblock(cb)
  local max_n = 0
  for line in (cb.text .. "\n"):gmatch("([^\r\n]*)[\r\n]") do
    local n = utf8.len(line) or #line
    if n > max_n then max_n = n end
  end
  
  local size_cmd
  if max_n <= 78 then
    size_cmd = "normalsize"
  elseif max_n <= 88 then
    size_cmd = "small"
  elseif max_n <= 99 then
    size_cmd = "footnotesize"
  elseif max_n <= 111 then
    size_cmd = "scriptsize"
  else
    size_cmd = "tiny"
    log_info(string.format("code block too wide: %d chars", max_n))
  end
  
  local body = cb.text
  if body:sub(-1) ~= "\n" then
    body = body .. "\n"
  end
  local latex_code = string.format("{\\%s\\begin{verbatim}\n%s\\end{verbatim}}\\par", size_cmd, body)
  return pandoc.RawBlock("latex", latex_code)
end

return {
  {
    Pandoc = function(doc)
      if FORMAT ~= "latex" then
        return doc
      end
      
      -- 1. Image swapping
      doc = doc:walk({
        Image = function(img)
          local src = img.src
          if src:match("%.png$") or src:match("%.jpg$") or src:match("%.jpeg$") then
            local no_ext = src:gsub("%.png$", ""):gsub("%.jpg$", ""):gsub("%.jpeg$", "")
            local pdf_src = no_ext .. ".pdf"
            local check_path = pdf_src
            if paper_dir ~= "" then
              check_path = paper_dir .. "/" .. pdf_src
            end
            if file_exists(check_path) then
              img.src = pdf_src
              log_info("Swapped image " .. src .. " to " .. pdf_src)
            end
          end
          return img
        end
      })
      
      -- 2. Drop duplicate title H1
      local meta_title = ""
      if doc.meta.title then
        meta_title = pandoc.utils.stringify(doc.meta.title):gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", ""):lower()
      end
      
      local dropped_first_h1 = false
      local new_blocks = {}
      for _, blk in ipairs(doc.blocks) do
        if not dropped_first_h1 and blk.t == "Header" and blk.level == 1 then
          local h_text = pandoc.utils.stringify(blk.content):gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", ""):lower()
          if meta_title ~= "" and meta_title:sub(1, #h_text) == h_text then
            dropped_first_h1 = true
            log_info("Dropped duplicate title H1: " .. h_text)
          else
            table.insert(new_blocks, blk)
          end
        else
          table.insert(new_blocks, blk)
        end
      end
      doc.blocks = new_blocks
      
      -- If document has NO level-1 header left, promote every Header by one level (level-1 minimum)
      local has_h1 = false
      for _, blk in ipairs(doc.blocks) do
        if blk.t == "Header" and blk.level == 1 then
          has_h1 = true
          break
        end
      end
      
      if not has_h1 then
        log_info("Promoting headers: no level-1 header found after title drop")
        doc = doc:walk({
          Header = function(h)
            if h.level > 1 then
              h.level = h.level - 1
            end
            return h
          end
        })
      end
      
      -- 3. Drop HorizontalRule
      new_blocks = {}
      for _, blk in ipairs(doc.blocks) do
        if blk.t ~= "HorizontalRule" then
          table.insert(new_blocks, blk)
        end
      end
      doc.blocks = new_blocks
      
      -- 4. Table captions & Para starting Table <label>: followed by Table or CodeBlock
      local function count_code_lines(s)
        if not s or s == "" then return 0 end
        local n = 0
        for _ in s:gmatch("\n") do
          n = n + 1
        end
        if s:sub(-1) ~= "\n" then
          n = n + 1
        end
        return n
      end

      local function estimate_table_needlines(tbl, has_caption)
        compute_table_widths(tbl)

        local num_cols = tbl.colspecs and #tbl.colspecs or 0
        local all_numeric = (num_cols > 0)
        if all_numeric then
          for _, cs in ipairs(tbl.colspecs) do
            if type(cs[2]) ~= "number" or cs[2] <= 0 then
              all_numeric = false
              break
            end
          end
        end

        local sum_row_lines = 0

        local function process_row(r)
          if not r or not r.cells then return end
          if not all_numeric then
            sum_row_lines = sum_row_lines + 1
            return
          end

          local row_lines = 1
          for c_idx, cell in ipairs(r.cells) do
            local cs = tbl.colspecs[c_idx]
            local w_i = (cs and type(cs[2]) == "number" and cs[2] > 0) and cs[2] or (1 / math.max(1, num_cols))
            local cap_i = math.max(4, math.floor(w_i * 100))
            local cell_text = pandoc.utils.stringify(cell.contents)
            local chars = utf8.len(cell_text) or #cell_text
            local cell_lines = math.ceil(chars / cap_i)
            if cell_lines > row_lines then
              row_lines = cell_lines
            end
          end
          sum_row_lines = sum_row_lines + row_lines
        end

        local function process_rows_list(rows)
          if not rows then return end
          for _, r in ipairs(rows) do
            process_row(r)
          end
        end

        if tbl.head and tbl.head.rows then
          process_rows_list(tbl.head.rows)
        end
        if tbl.bodies then
          for _, b in ipairs(tbl.bodies) do
            if b.head then process_rows_list(b.head) end
            if b.body then process_rows_list(b.body) end
          end
        end
        if tbl.foot and tbl.foot.rows then
          process_rows_list(tbl.foot.rows)
        end

        local k = 3 + sum_row_lines + (has_caption and 2 or 0)
        -- A table estimated at more than NEEDLINES_MAX lines may split (longtable repeats
        -- its header); it only needs room for caption + header + a few rows. A larger
        -- guard left pages 20-40 % empty (v2: guards of 13-30 lines before long tables).
        if k > needlines_max then
          k = needlines_split
        end
        return k
      end

      local function insert_guarded(blocks, guarded_items, k)
        local h_count = 0
        local insert_pos = #blocks + 1
        for i = #blocks, 1, -1 do
          if blocks[i].t == "Header" then
            h_count = h_count + 1
            insert_pos = i
          else
            break
          end
        end
        local k_total = k + (3 * h_count)
        table.insert(blocks, insert_pos, pandoc.RawBlock("latex", "\\needlines{" .. k_total .. "}"))
        for _, item in ipairs(guarded_items) do
          table.insert(blocks, item)
        end
      end

      new_blocks = {}
      local idx = 1
      while idx <= #doc.blocks do
        local blk = doc.blocks[idx]
        local next_blk = doc.blocks[idx + 1]
        if blk.t == "Para" and next_blk and next_blk.t == "Table" then
          local text = pandoc.utils.stringify(blk.content)
          if text:match("^Table%s+[A-Z]*%d+[a-z]?:") then
            local modified_inlines = format_table_caption_inlines(blk.content)
            next_blk.caption.long = { pandoc.Plain(modified_inlines) }
            local k = estimate_table_needlines(next_blk, true)
            insert_guarded(new_blocks, { next_blk }, k)
            idx = idx + 2
          else
            table.insert(new_blocks, blk)
            idx = idx + 1
          end
        elseif blk.t == "Para" and next_blk and next_blk.t == "CodeBlock" then
          local text = pandoc.utils.stringify(blk.content)
          if text:match("^Table%s+[A-Z]*%d+[a-z]?:") then
            local nlines = count_code_lines(next_blk.text)
            -- A verbatim block repeats no header when it splits (v2 test: capping this
            -- guard left D7's closing rule alone atop p31), so keep it whole up to 25.
            local k = math.min(3 + nlines, 25)
            blk.content = format_table_caption_inlines(blk.content)
            insert_guarded(new_blocks, { blk, next_blk }, k)
            idx = idx + 2
          else
            table.insert(new_blocks, blk)
            idx = idx + 1
          end
        elseif blk.t == "Table" then
          local has_caption = (blk.caption and blk.caption.long and #blk.caption.long > 0) or
                              (blk.caption and #pandoc.utils.stringify(blk.caption) > 0)
          local k = estimate_table_needlines(blk, has_caption)
          insert_guarded(new_blocks, { blk }, k)
          idx = idx + 1
        else
          table.insert(new_blocks, blk)
          idx = idx + 1
        end
      end
      doc.blocks = new_blocks
      
      -- 5. Figure captions
      doc = doc:walk({
        Figure = format_figure_caption
      })
      
      -- 6. Wide table column width recomputation (BEFORE Code -> RawInline)
      doc = doc:walk({
        Table = compute_table_widths
      })
      
      -- 7. Code spans in Headers are left as pandoc Code. Pandoc's writer then sets
      --    \texttt{..} in the heading and a plain PDF-string for the bookmark. A RawInline
      --    here made pandoc wrap the heading in its own \texorpdfstring and drop the raw
      --    part from the bookmark ("2.4 Metrics, and the floor of " without goal_pass).
      local function caret_str(el)
        local n1, n2, rest = el.text:match("^(%d+)%^(%d+)(.*)$")
        if n1 and n2 then
          local res = { pandoc.Str(n1), pandoc.Superscript({ pandoc.Str(n2) }) }
          if rest and rest ~= "" then
            table.insert(res, pandoc.Str(rest))
          end
          return res
        end
        return el
      end

      -- 8. Code spans outside Headers, literal carets, and CodeBlocks. Top-down so a
      --    Header's children can be skipped (returning false as second value).
      doc = doc:walk({
        traverse = "topdown",
        Header = function(h)
          h.content = h.content:walk({ Str = caret_str })
          return h, false
        end,
        Code = function(c)
          local escaped = latex_escape_code(c.text, false)
          return pandoc.RawInline("latex", string.format("\\texttt{%s}", escaped))
        end,
        Str = caret_str,
        CodeBlock = format_codeblock
      })
      
      -- 9. Bibliography before appendices
      local appendix_idx = nil
      for b_idx, blk in ipairs(doc.blocks) do
        if blk.t == "Header" and (blk.level == 1 or blk.level == 2) then
          local h_text = pandoc.utils.stringify(blk.content):gsub("^%s+", "")
          if h_text:match("^Appendix") then
            appendix_idx = b_idx
            break
          end
        end
      end
      
      if appendix_idx then
        table.insert(doc.blocks, appendix_idx, pandoc.RawBlock("latex", "\\bibliography{bibliography}"))
        doc.meta["refs-placed"] = true
      end
      
      return doc
    end
  }
}
