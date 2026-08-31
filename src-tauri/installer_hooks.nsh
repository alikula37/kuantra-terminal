; Kuantra Terminal NSIS Process Cleanup Hooks
; Gracefully terminates existing running instances before installation, update, or uninstallation

!macro customInit
  DetailPrint "Stopping running Kuantra Terminal processes..."
  nsExec::Exec 'taskkill /F /IM "kuantra-backend.exe" /T'
  nsExec::Exec 'taskkill /F /IM "kuantra-backend-x86_64-pc-windows-msvc.exe" /T'
  nsExec::Exec 'taskkill /F /IM "Kuantra Terminal.exe" /T'
  nsExec::Exec 'taskkill /F /IM "kuantra-terminal.exe" /T'
!macroend

!macro customInstall
  DetailPrint "Ensuring process teardown before writing files..."
  nsExec::Exec 'taskkill /F /IM "kuantra-backend.exe" /T'
  nsExec::Exec 'taskkill /F /IM "kuantra-backend-x86_64-pc-windows-msvc.exe" /T'
  nsExec::Exec 'taskkill /F /IM "Kuantra Terminal.exe" /T'
  nsExec::Exec 'taskkill /F /IM "kuantra-terminal.exe" /T'
!macroend

!macro customUnInstall
  DetailPrint "Stopping Kuantra Terminal before uninstallation..."
  nsExec::Exec 'taskkill /F /IM "kuantra-backend.exe" /T'
  nsExec::Exec 'taskkill /F /IM "kuantra-backend-x86_64-pc-windows-msvc.exe" /T'
  nsExec::Exec 'taskkill /F /IM "Kuantra Terminal.exe" /T'
  nsExec::Exec 'taskkill /F /IM "kuantra-terminal.exe" /T'
!macroend