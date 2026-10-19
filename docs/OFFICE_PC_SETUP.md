# Continue on another Windows PC

Install Git and Python 3.11, then open PowerShell in your preferred work folder:

```powershell
git clone https://github.com/Aviseka00/SOP-trainer.git
cd SOP-trainer
.\INSTALL_WINDOWS.bat
.\START_WINDOWS.bat
```

Open http://127.0.0.1:8501. The app starts with Upload SOP → Generate content → Add voice → Design video → Generate training video. Use Advanced tools for additional controls.

The repository contains source, tests, documentation, a fictional SOP and original fictional presenter portraits. Private SOPs/projects, recorded voices, saved API keys, generated videos, dependencies and model weights are excluded. Set up your provider keys on the new PC through the app. Windows-encrypted credentials from another computer cannot be reused. Cloud access and credits belong to the provider account; local installed voices may differ between PCs.

Use `INSTALL_AI_PRESENTER.bat` only if you need the optional local SadTalker engine. It downloads a separate runtime and models; it is not needed for the basic app or cloud presenters. CPU presenter generation is slow. No GPU performance is assumed for the new computer.

To check the installation, run `DIAGNOSE_WINDOWS.bat` and `TEST_WINDOWS.bat`. The optional cached local-avatar benchmark can skip when its fixture is absent.

For later updates:

```powershell
git pull --ff-only
.\INSTALL_WINDOWS.bat
```

If you changed source locally, commit your work before pulling. Restart the app after updating Python modules. Runtime folders are created automatically; transfer any private project/media files separately through an approved private channel when needed.
