-- Name: ai_summarize.applescript
-- Author: HuangFuSL
-- Date: 2025-06-07
-- Description: BibDesk Script Hook to summarize paper into `annote` field
-- BibDesk Script Hook: Close Editor Window
--
-- HOW TO USE
--   1. Place **this AppleScript** and `ai_summarize.py` in the same
--      directory (e.g. ~/Library/Application Support/BibDesk/Scripts/).
--   2. Edit `ai_summarize.py` to configure the API key and model to use.
--   3. In BibDesk > Preferences > Script Hooks, attach this script to the
--      "Close Editor Window" hook.
--
-- Tested with BibDesk 1.9.5 on macOS 15.5 Sequoia

--------------------------------------------------------------------------------
-- USER CONFIGURABLE PROPERTIES
--------------------------------------------------------------------------------
property pythonScriptName : "ai_summarize.py"

--------------------------------------------------------------------------------
-- MAIN HANDLER
--------------------------------------------------------------------------------
using terms from application "BibDesk"
  on perform BibDesk action with publications thePubs for script hook theScriptHook
    if (name of theScriptHook) is not "Close Editor Window" then return

    -- Initialize Python environment
    set pythonBinary to do shell script "/usr/bin/which python3"
    if pythonBinary is "" then error "python3 not found in PATH"

    set scriptPath to POSIX path of (path to me)
    set AppleScript's text item delimiters to "/"
    set scriptDir to (text items 1 thru -2 of scriptPath) as string
    set AppleScript's text item delimiters to ""

    set venvDir to scriptDir & "/.venv"
    set venvPython to venvDir & "/bin/python"
    set venvExists to (do shell script "[ -d " & quoted form of venvDir & " ] && echo 1 || echo 0") as integer
    if venvExists = 0 then
      do shell script quoted form of pythonBinary & " -m venv " & quoted form of venvDir
      do shell script quoted form of venvPython & " -m pip install --upgrade pip"
      set reqPath to scriptDir & "/requirements.txt"
      set reqExists to (do shell script "[ -f " & quoted form of reqPath & " ] && echo 1 || echo 0") as integer
      if reqExists = 1 then
        do shell script quoted form of venvPython & " -m pip install -r " & quoted form of reqPath
      end if
    end if

    set pythonBinary to venvPython
    set pythonScriptPath to scriptDir & "/" & pythonScriptName

    -- Process publications
    repeat with aPub in thePubs
      try
        -- 1. Grab current annote value
        tell aPub
          set annoteField to field "annote"
          set currentAnnote to (value of annoteField) as text
        end tell
        if currentAnnote is not "" then return

        -- 2. Build absolute path to the attached PDF
        set pdfPath to ""
        tell aPub
          set linkedFiles to linked files -- list of file aliases
        end tell
        repeat with f in linkedFiles
          set p to POSIX path of f
          if p ends with ".pdf" then
            set pdfPath to p
            exit repeat
          end if
        end repeat
        if pdfPath is "" then return

        -- 3. Execute helper and capture stdout
        set shellCmd to quoted form of pythonBinary & space & quoted form of pythonScriptPath & space & quoted form of pdfPath
        set newAnnote to do shell script shellCmd

        -- 4. Update annote if we received something back
        if newAnnote is not "" then
          tell aPub to set value of field "annote" to newAnnote
        end if

      on error errMsg number errNum
        display dialog "Annote post process script failed (" & errNum & "): " & errMsg
      end try
    end repeat
  end perform BibDesk action with publications
end using terms from
