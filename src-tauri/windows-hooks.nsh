!macro NSIS_HOOK_POSTINSTALL
  CreateShortCut "$DESKTOP\Skill-Desk.lnk" "$INSTDIR\Skill-Desk.exe" "" "$INSTDIR\Skill-Desk.exe" 0
!macroend
!macro NSIS_HOOK_PREUNINSTALL
  Delete "$DESKTOP\Skill-Desk.lnk"
!macroend
