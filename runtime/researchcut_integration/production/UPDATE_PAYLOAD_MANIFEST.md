# ResearchCut 2.1 update payload manifest

The official 2.0-to-2.1 update ZIP contains `APPLY_UPDATE_2.1.ps1`, this manifest,
the employee guide and a `payload` folder. The updater copies only the files in
that payload, after first backing up every replaced target file.

## Program files

- `server.js`
- `renderer.js`
- `automation-catalog.js`
- `package.json`
- `public/app.js`
- `public/styles.css`
- `CHECK_SYSTEM.bat`

## Documentation

- `README.md`
- `UPDATE_NOTES_2.1.md`
- `OFFICE_AND_EMPLOYEE_DEPLOYMENT.md`
- `EMPLOYEE_UPDATE_GUIDE.md`
- `SETUP_NEW_WINDOWS_LAPTOP.md`
- `VALIDATION_REPORT.md`

The update deliberately does not delete or replace `backgrounds`, `tools`,
`node_modules`, or `%LOCALAPPDATA%\ResearchCut Editor`. New background files
therefore remain employee-controlled and existing projects remain intact.
