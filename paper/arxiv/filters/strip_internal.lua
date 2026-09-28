-- strip_internal.lua — remove internal claims-ledger ids (PUBLIC mode default)

local log_path = os.getenv("STRIP_LOG")
if not log_path or log_path == "" then
  log_path = "strip_internal.log"
end

local keep_ids = (os.getenv("KEEP_IDS") == "1")

local removed_ids_count = 0
local places_count = 0
local residual_count = 0
local dropped_columns_count = 0

local function log_line(line)
  local f = io.open(log_path, "a")
  if f then
    f:write(line .. "\n")
    f:close()
  end
end

local function log_event(kind, p1, p2)
  if p2 ~= nil then
    log_line(string.format("%s\t%s\t%s", kind, p1, p2))
  elseif p1 ~= nil then
    log_line(string.format("%s\t%s", kind, p1))
  else
    log_line(kind)
  end
end

-- ID grammar implementation
local function split_dashes(s)
  local parts = {}
  for p in s:gmatch("[^%-]+") do
    table.insert(parts, p)
  end
  return parts
end

local function is_base_id(s)
  if not s or s == "" then return false end
  if s:sub(1,1) == "-" or s:sub(-1,-1) == "-" then return false end
  local parts = split_dashes(s)
  if #parts < 2 then return false end
  
  -- part 1: [A-Z][A-Z0-9]*
  if not parts[1]:match("^[A-Z][A-Z0-9]*$") then return false end
  
  -- middle parts: [A-Z0-9]+
  for i = 2, #parts - 1 do
    if not parts[i]:match("^[A-Z0-9]+$") then return false end
  end
  
  -- last part: exactly two digits optionally followed by ONE lowercase letter
  if not parts[#parts]:match("^[0-9][0-9][a-z]?$") then return false end
  
  return true
end

local function is_id(s)
  if not s or s == "" then return false end
  local base, suffix = s:match("^(.-)%.%.(.+)$")
  if base and suffix then
    if not is_base_id(base) then return false end
    if suffix:match("^[0-9][0-9]$") or is_base_id(suffix) then
      return true
    end
    return false
  end
  return is_base_id(s)
end

local function is_id_item(s)
  s = s:gsub("^%s+", ""):gsub("%s+$", "")
  if s == "" then return false end
  if is_id(s) then return true end
  local id1, id2 = s:match("^([A-Za-z0-9%-%.]+)%s+to%s+([A-Za-z0-9%-%.]+)$")
  if id1 and id2 and is_id(id1) and is_id(id2) then
    return true
  end
  return false
end

local function parse_id_list(s)
  if not s then return false, nil end
  s = s:gsub("^%s+", ""):gsub("%s+$", "")
  if s == "" then return false, nil end
  
  local norm = s:gsub(",%s+and%s+", ", "):gsub("%s+and%s+", ", ")
  local items = {}
  local ids_found = {}
  for item in norm:gmatch("[^,]+") do
    item = item:gsub("^%s+", ""):gsub("%s+$", "")
    if item ~= "" then
      if not is_id_item(item) then
        return false, nil
      end
      table.insert(items, item)
      local id1, id2 = item:match("^([A-Za-z0-9%-%.]+)%s+to%s+([A-Za-z0-9%-%.]+)$")
      if id1 and id2 then
        table.insert(ids_found, id1)
        table.insert(ids_found, id2)
      else
        table.insert(ids_found, item)
      end
    end
  end
  if #items == 0 then return false, nil end
  return true, ids_found
end

-- Check if a string contains any candidate ID substring
local function string_contains_id(s)
  if not s then return false end
  for token in s:gmatch("[A-Za-z0-9%-%.]+") do
    token = token:gsub("%.+$", ""):gsub("%-+$", "")
    if is_id(token) then return true end
  end
  return false
end

-- Top-level delimiter split respecting () and []
local function split_top_level(text, delims)
  local segs = {}
  local cur = {}
  local p_depth = 0
  local b_depth = 0
  local len = #text
  local i = 1
  while i <= len do
    local c = text:sub(i, i)
    if c == "(" then
      p_depth = p_depth + 1
      table.insert(cur, c)
    elseif c == ")" then
      p_depth = math.max(0, p_depth - 1)
      table.insert(cur, c)
    elseif c == "[" then
      b_depth = b_depth + 1
      table.insert(cur, c)
    elseif c == "]" then
      b_depth = math.max(0, b_depth - 1)
      table.insert(cur, c)
    elseif delims[c] and p_depth == 0 and b_depth == 0 then
      table.insert(segs, table.concat(cur))
      cur = {}
    else
      table.insert(cur, c)
    end
    i = i + 1
  end
  table.insert(segs, table.concat(cur))
  return segs
end

-- Tidy whitespace and punctuation
local function tidy_text(s)
  s = s:gsub("[ \t]+", " ")
  s = s:gsub("%s+([%.,;:%)])", "%1")
  s = s:gsub("%(%s+", "(")
  s = s:gsub("%([;,]%s*", "(")
  s = s:gsub("[;,]%s*%)", ")")
  s = s:gsub(";%s*;", ";")
  s = s:gsub(",%s*,", ",")
  s = s:gsub("%s*%(%)", "")
  s = s:gsub("[ \t]+", " ")
  return s
end

-- Process parenthetical groups
local function process_parentheticals(str, orig_context)
  local len = #str
  local out = {}
  local i = 1
  while i <= len do
    local c = str:sub(i, i)
    if c == "(" then
      local start_p = i
      local p_depth = 1
      local b_depth = 0
      local j = i + 1
      while j <= len and p_depth > 0 do
        local cj = str:sub(j, j)
        if cj == "(" then p_depth = p_depth + 1
        elseif cj == ")" then p_depth = p_depth - 1
        elseif cj == "[" then b_depth = b_depth + 1
        elseif cj == "]" then b_depth = math.max(0, b_depth - 1)
        end
        j = j + 1
      end
      
      if p_depth == 0 then
        local close_p = j - 1
        local inner = str:sub(start_p + 1, close_p - 1)
        
        -- Split at top-level ;
        local segs = split_top_level(inner, { [";"] = true })
        local kept_segs = {}
        local segs_removed_ids = {}
        
        for _, seg in ipairs(segs) do
          local trimmed = seg:gsub("^%s+", ""):gsub("%s+$", "")
          local is_list, ids = parse_id_list(trimmed)
          if is_list then
            for _, id in ipairs(ids) do table.insert(segs_removed_ids, id) end
          else
            -- Check if mixed comma list
            local items = split_top_level(trimmed, { [","] = true })
            if #items > 1 then
              local kept_items = {}
              local has_id = false
              local has_non_id = false
              local item_ids = {}
              
              for _, item in ipairs(items) do
                local it_trimmed = item:gsub("^%s+", ""):gsub("%s+$", "")
                local it_is_id, it_id_list = parse_id_list(it_trimmed)
                if it_is_id then
                  has_id = true
                  for _, id in ipairs(it_id_list) do table.insert(item_ids, id) end
                else
                  has_non_id = true
                  table.insert(kept_items, it_trimmed)
                end
              end
              
              if has_id and has_non_id then
                for _, id in ipairs(item_ids) do table.insert(segs_removed_ids, id) end
                table.insert(kept_segs, table.concat(kept_items, ", "))
              else
                table.insert(kept_segs, trimmed)
              end
            else
              table.insert(kept_segs, trimmed)
            end
          end
        end
        
        if #segs_removed_ids > 0 then
          log_event("REMOVED", table.concat(segs_removed_ids, ","), orig_context:sub(1, 80))
          places_count = places_count + 1
          removed_ids_count = removed_ids_count + #segs_removed_ids
        end
        
        if #kept_segs == 0 then
          -- Drop whole parenthetical group AND single space before it if present
          if #out > 0 and out[#out] == " " then
            table.remove(out)
          end
        else
          table.insert(out, "(" .. table.concat(kept_segs, "; ") .. ")")
        end
        
        i = close_p + 1
      else
        table.insert(out, c)
        i = i + 1
      end
    else
      table.insert(out, c)
      i = i + 1
    end
  end
  return table.concat(out)
end

-- Process Rule 2: Trailing tag outside parens (; <id list> followed by ., ), or end)
local function process_trailing_tag(str, orig_context)
  local segs = split_top_level(str, { [";"] = true })
  if #segs > 1 then
    local last_seg = segs[#segs]
    local term = ""
    local body = last_seg:gsub("^%s+", ""):gsub("%s+$", "")
    if body:sub(-1) == "." or body:sub(-1) == ")" then
      term = body:sub(-1)
      body = body:sub(1, -2):gsub("%s+$", "")
    end
    local is_list, ids = parse_id_list(body)
    if is_list then
      table.remove(segs)
      log_event("REMOVED", table.concat(ids, ","), orig_context:sub(1, 80))
      places_count = places_count + 1
      removed_ids_count = removed_ids_count + #ids
      return table.concat(segs, "; ") .. term
    end
  end
  return str
end

-- Process Rule 3: Source: <id list>. or Sources: <id list>.
local function find_sentence_dot(str, start_idx)
  local len = #str
  local i = start_idx
  while i <= len do
    local c = str:sub(i, i)
    if c == "." then
      local is_double_dot = false
      if i > 1 and str:sub(i - 1, i - 1) == "." then
        is_double_dot = true
      elseif i < len and str:sub(i + 1, i + 1) == "." then
        is_double_dot = true
      end
      
      if not is_double_dot then
        if i == len or str:sub(i + 1, i + 1):match("%s") then
          return i
        end
      end
    end
    i = i + 1
  end
  return nil
end

local function process_source_sentence(str, orig_context)
  local search_pos = 1
  while search_pos <= #str do
    local s_start, s_end = str:find("[Ss]ources?:", search_pos)
    if not s_start then
      break
    end
    
    if s_start == 1 or str:sub(s_start - 1, s_start - 1):match("%s") then
      local body_start = s_end + 1
      while body_start <= #str and str:sub(body_start, body_start):match("%s") do
        body_start = body_start + 1
      end
      
      local dot_pos = find_sentence_dot(str, body_start)
      if dot_pos then
        local body = str:sub(body_start, dot_pos - 1)
        local is_list, ids = parse_id_list(body)
        if is_list then
          log_event("REMOVED", table.concat(ids, ","), orig_context:sub(1, 80))
          places_count = places_count + 1
          removed_ids_count = removed_ids_count + #ids
          
          local del_start = s_start
          if del_start > 1 and str:sub(del_start - 1, del_start - 1):match("%s") then
            del_start = del_start - 1
          end
          
          local prefix = str:sub(1, del_start - 1)
          local suffix = str:sub(dot_pos + 1)
          if del_start == 1 then
            suffix = suffix:gsub("^%s+", "")
          end
          
          str = prefix .. suffix
          search_pos = math.max(1, del_start)
        else
          search_pos = s_end + 1
        end
      else
        search_pos = s_end + 1
      end
    else
      search_pos = s_end + 1
    end
  end
  return str
end

-- Scan remaining string for RESIDUAL IDs
local function scan_residual_ids(str)
  local len = #str
  local p_depth = 0
  local b_depth = 0
  local i = 1
  while i <= len do
    local c = str:sub(i, i)
    if c == "(" then p_depth = p_depth + 1
    elseif c == ")" then p_depth = math.max(0, p_depth - 1)
    elseif c == "[" then b_depth = b_depth + 1
    elseif c == "]" then b_depth = math.max(0, b_depth - 1)
    end
    
    if c:match("[A-Za-z0-9]") and (i == 1 or not str:sub(i-1, i-1):match("[A-Za-z0-9_%-]")) then
      local start_idx = i
      local end_idx = i
      while end_idx <= len and str:sub(end_idx, end_idx):match("[A-Za-z0-9%-%.]") do
        end_idx = end_idx + 1
      end
      local token = str:sub(start_idx, end_idx - 1)
      -- trim any trailing punctuation like . or -
      token = token:gsub("%.+$", ""):gsub("%-+$", "")
      if is_id(token) then
        local ctx_start = math.max(1, start_idx - 40)
        local ctx_end = math.min(len, start_idx + #token + 40 - 1)
        local ctx = str:sub(ctx_start, ctx_end)
        log_event("RESIDUAL", token, ctx)
        residual_count = residual_count + 1
      end
      i = end_idx
    else
      i = i + 1
    end
  end
end

-- Strip Inlines list
local function strip_inlines(inlines)
  if keep_ids then return inlines end
  if not inlines or #inlines == 0 then return inlines end
  
  -- Check if any Str contains an ID candidate
  local has_any_id = false
  for _, el in ipairs(inlines) do
    if el.t == "Str" and string_contains_id(el.text) then
      has_any_id = true
      break
    end
  end
  if not has_any_id then return inlines end
  
  -- Flatten to string with placeholders
  local placeholders = {}
  local parts = {}
  local p_idx = 0
  
  for _, el in ipairs(inlines) do
    if el.t == "Str" then
      table.insert(parts, el.text)
    elseif el.t == "Space" or el.t == "SoftBreak" or el.t == "LineBreak" then
      table.insert(parts, " ")
    else
      p_idx = p_idx + 1
      local ph = utf8.char(0xE000 + p_idx)
      placeholders[ph] = el
      table.insert(parts, ph)
    end
  end
  
  local full_str = table.concat(parts)
  local orig_context = full_str
  
  -- Rule 1: Parenthetical groups
  full_str = process_parentheticals(full_str, orig_context)
  
  -- Rule 2: Trailing tag outside parens
  full_str = process_trailing_tag(full_str, orig_context)
  
  -- Rule 3: Source: <id list>.
  full_str = process_source_sentence(full_str, orig_context)
  
  -- Rule 4: Tidy
  full_str = tidy_text(full_str)
  
  -- Rule 5: Log residual IDs
  scan_residual_ids(full_str)
  
  -- Rebuild Inlines from full_str
  local new_inlines = {}
  local len = #full_str
  local i = 1
  while i <= len do
    local c = full_str:sub(i, i)
    if c == " " or c == "\t" or c == "\n" or c == "\r" then
      while i <= len and full_str:sub(i, i):match("%s") do
        i = i + 1
      end
      table.insert(new_inlines, pandoc.Space())
    else
      local buf = {}
      while i <= len and not full_str:sub(i, i):match("%s") do
        local ph_candidate = full_str:sub(i, i + 2) -- UTF-8 3-byte char
        if placeholders[ph_candidate] then
          if #buf > 0 then
            table.insert(new_inlines, pandoc.Str(table.concat(buf)))
            buf = {}
          end
          table.insert(new_inlines, placeholders[ph_candidate])
          i = i + 3
        else
          table.insert(buf, full_str:sub(i, i))
          i = i + 1
        end
      end
      if #buf > 0 then
        table.insert(new_inlines, pandoc.Str(table.concat(buf)))
      end
    end
  end
  
  -- remove leading/trailing space in inlines if original didn't have it
  if #new_inlines > 0 and new_inlines[1].t == "Space" and inlines[1].t ~= "Space" then
    table.remove(new_inlines, 1)
  end
  if #new_inlines > 0 and new_inlines[#new_inlines].t == "Space" and inlines[#inlines].t ~= "Space" then
    table.remove(new_inlines)
  end
  
  return new_inlines
end

-- Table processing
local function has_col_span_gt_1(tbl)
  local function check_rows(rows)
    if not rows then return false end
    for _, r in ipairs(rows) do
      for _, c in ipairs(r.cells) do
        if c.col_span and c.col_span > 1 then return true end
      end
    end
    return false
  end
  if check_rows(tbl.head.rows) then return true end
  for _, b in ipairs(tbl.bodies) do
    if check_rows(b.head) or check_rows(b.body) then return true end
  end
  if check_rows(tbl.foot.rows) then return true end
  return false
end

local function process_table(tbl)
  if keep_ids then return tbl end
  
  local caption_text = pandoc.utils.stringify(tbl.caption)
  if caption_text == "" and #tbl.head.rows > 0 and #tbl.head.rows[1].cells > 0 then
    caption_text = pandoc.utils.stringify(tbl.head.rows[1].cells[1].contents)
  end
  
  local function process_cells_in_rows(rows)
    if not rows then return end
    for _, r in ipairs(rows) do
      for _, c in ipairs(r.cells) do
        local cell_text = pandoc.utils.stringify(c.contents):gsub("^%s+", ""):gsub("%s+$", "")
        local is_list, ids = parse_id_list(cell_text)
        if is_list then
          c.contents = { pandoc.Plain({}) }
          log_event("EMPTIED_CELL", table.concat(ids, ","), caption_text)
          places_count = places_count + 1
          removed_ids_count = removed_ids_count + #ids
        end
      end
    end
  end
  
  process_cells_in_rows(tbl.head.rows)
  for _, b in ipairs(tbl.bodies) do
    process_cells_in_rows(b.head)
    process_cells_in_rows(b.body)
  end
  process_cells_in_rows(tbl.foot.rows)
  
  -- Drop columns if applicable
  if not has_col_span_gt_1(tbl) and #tbl.head.rows > 0 then
    local target_headers = {
      ["source"] = true,
      ["sources"] = true,
      ["ledger"] = true,
      ["ledger id"] = true,
      ["ledger ids"] = true,
      ["key"] = true,
      ["keys"] = true,
    }
    
    local num_cols = #tbl.colspecs
    for col_idx = num_cols, 1, -1 do
      local h_cell = tbl.head.rows[1].cells[col_idx]
      if h_cell then
        local h_text = pandoc.utils.stringify(h_cell.contents):gsub("^%s+", ""):gsub("%s+$", "")
        if target_headers[h_text:lower()] then
          local all_match = true
          local n_body_cells = 0
          
          for _, b in ipairs(tbl.bodies) do
            local rows = b.body
            for _, r in ipairs(rows) do
              n_body_cells = n_body_cells + 1
              local cell = r.cells[col_idx]
              if cell then
                local ct = pandoc.utils.stringify(cell.contents):gsub("^%s+", ""):gsub("%s+$", "")
                if ct ~= "" and ct ~= "—" and ct ~= "-" and not parse_id_list(ct) then
                  all_match = false
                end
              end
            end
          end
          
          if all_match and n_body_cells > 0 then
            table.remove(tbl.colspecs, col_idx)
            for _, r in ipairs(tbl.head.rows) do table.remove(r.cells, col_idx) end
            for _, b in ipairs(tbl.bodies) do
              for _, r in ipairs(b.head) do table.remove(r.cells, col_idx) end
              for _, r in ipairs(b.body) do table.remove(r.cells, col_idx) end
            end
            for _, r in ipairs(tbl.foot.rows) do table.remove(r.cells, col_idx) end
            
            -- Renormalise numeric widths
            local old_sum = 0
            local all_numeric = true
            for _, cs in ipairs(tbl.colspecs) do
              if type(cs[2]) == "number" then
                old_sum = old_sum + cs[2]
              else
                all_numeric = false
              end
            end
            if all_numeric and old_sum > 0 then
              for _, cs in ipairs(tbl.colspecs) do
                cs[2] = cs[2] / old_sum
              end
            end
            
            log_event("DROPPED_COLUMN", h_text, tostring(n_body_cells))
            dropped_columns_count = dropped_columns_count + 1
          end
        end
      end
    end
  end
  
  return tbl
end

-- Header identifiers recomputation.
-- Only a header whose text contained an id is re-identified (its auto identifier embeds
-- the id). Every other identifier, including an explicit {#sec:..} that links point at,
-- is left untouched. The pre-pass below marks the headers and records every identifier
-- in use, so a recomputed one cannot collide with an untouched one.
local REID_ATTR = "strip-reid"
local used_identifiers = {}

local function mark_header(elem)
  if keep_ids then return elem end
  if elem.identifier and elem.identifier ~= "" then
    used_identifiers[elem.identifier] = true
  end
  if string_contains_id(pandoc.utils.stringify(elem.content)) then
    elem.attributes[REID_ATTR] = "1"
    return elem
  end
  return nil
end

local function process_header(elem)
  if keep_ids then return elem end
  if elem.attributes[REID_ATTR] == nil then return nil end
  elem.attributes[REID_ATTR] = nil
  local text = pandoc.utils.stringify(elem.content):lower()
  text = text:gsub("%s+", "-")
  text = text:gsub("[^a-z0-9._%-]", "")
  text = text:gsub("^[^a-z]+", ""):gsub("%-+$", "")   -- as pandoc: start at the first letter
  if text == "" then text = "section" end
  local candidate = text
  local n = 0
  while used_identifiers[candidate] and candidate ~= elem.identifier do
    n = n + 1
    candidate = text .. "-" .. tostring(n)
  end
  if elem.identifier and elem.identifier ~= "" then
    used_identifiers[elem.identifier] = nil
  end
  used_identifiers[candidate] = true
  elem.identifier = candidate
  return elem
end

local function process_meta(meta)
  if keep_ids then return meta end
  if meta.title then
    if meta.title.t == "MetaInlines" then
      meta.title = pandoc.MetaInlines(strip_inlines(meta.title))
    elseif type(meta.title) == "table" and meta.title[1] and meta.title[1].t then
      meta.title = strip_inlines(meta.title)
    end
  end
  if meta.abstract then
    if meta.abstract.t == "MetaBlocks" then
      for _, blk in ipairs(meta.abstract) do
        if blk.content then blk.content = strip_inlines(blk.content) end
      end
    elseif meta.abstract.t == "MetaInlines" then
      meta.abstract = pandoc.MetaInlines(strip_inlines(meta.abstract))
    elseif type(meta.abstract) == "table" then
      for _, blk in ipairs(meta.abstract) do
        if blk.content then blk.content = strip_inlines(blk.content) end
      end
    end
  end
  return meta
end

local function split_first_line(text)
  local first_line, rest = text:match("^([^\r\n]*)[\r\n]+(.*)$")
  if not first_line then
    first_line = text
    rest = ""
  end
  return first_line, rest
end

local function process_codeblock(cb)
  local first_line, rest = split_first_line(cb.text)
  if first_line:match("^Table%s+[A-Z]*%d+[a-z]?:") then
    local parsed = pandoc.read(first_line, "markdown")
    local inlines = {}
    if parsed.blocks and #parsed.blocks > 0 and parsed.blocks[1].content then
      inlines = parsed.blocks[1].content
    else
      inlines = { pandoc.Str(first_line) }
    end
    if not keep_ids then
      inlines = strip_inlines(inlines)
    end
    local para = pandoc.Para(inlines)
    local remaining_cb = pandoc.CodeBlock(rest, cb.attr)
    return { para, remaining_cb }
  end
  return cb
end

return {
  {
    Header = mark_header,
  },
  {
    Meta = process_meta,
    Inlines = strip_inlines,
    Table = process_table,
    Header = process_header,
    CodeBlock = process_codeblock,
  },
  {
    Pandoc = function(doc)
      if keep_ids then
        log_event("INFO", "KEEP_IDS=1, nothing removed")
        log_event("SUMMARY", "removed_ids=0\tplaces=0\tresidual=0\tdropped_columns=0")
      else
        local summary = string.format("removed_ids=%d\tplaces=%d\tresidual=%d\tdropped_columns=%d",
          removed_ids_count, places_count, residual_count, dropped_columns_count)
        log_event("SUMMARY", summary)
      end
      return doc
    end
  }
}
