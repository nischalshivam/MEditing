# ResearchCut office and employee deployment

## Can two or three people use it at the same time?

Yes, when every employee has ResearchCut installed on their own laptop or Windows account and works on their own local projects. This is the recommended office setup.

Current ResearchCut is local-first:

- the server listens only on 127.0.0.1;
- the project library belongs to the Windows user running the app;
- source media and renders stay on that PC;
- there is no cloud database, account system or central collaboration server.

## Recommended office model

Install one copy per employee laptop:

    Employee laptop A -> local ResearchCut -> local projects/renders
    Employee laptop B -> local ResearchCut -> local projects/renders
    Employee laptop C -> local ResearchCut -> local projects/renders

This allows all employees to work simultaneously without interfering with each other. Give each employee the same version ZIP and update kit.

## Same laptop

One running ResearchCut server can be opened in multiple browser tabs. Different projects can technically be edited, but CPU, RAM, storage and render jobs are shared.

Do not edit the same project simultaneously in two tabs or by two people. ResearchCut detects revision conflicts, but it is not a collaborative multi-user timeline and does not merge two editors' changes.

On a shared workstation:

- use separate Windows accounts when practical;
- one employee should own a project at a time;
- queue renders instead of running multiple 4K jobs together;
- close the project before handing it to another editor.

## One central office server

Not supported in the current local build. Other laptops cannot connect because the app intentionally binds to localhost, and it has no login/permission/project-lock service.

A true shared-office edition would require:

- authenticated users and roles;
- LAN or cloud hosting;
- central database and media storage;
- project ownership/locking;
- simultaneous-edit conflict handling;
- backup/restore policy;
- render-worker scheduling.

Do not expose the existing localhost server to the network by changing its host address. That would bypass the missing security and collaboration controls.

## Sharing a project between employees

The safe manual method is to close ResearchCut and copy the complete project folder from:

    %LOCALAPPDATA%\ResearchCut Editor\projects\<project-id>

Copying only project.json is not enough because imported media, VText files and renders live beside it.

Never copy into a project folder while ResearchCut is running. Prefer whole-library backup/restore for a replacement laptop.

## How updates should be distributed

For every release, distribute:

- complete version ZIP for new installations;
- small update ZIP for existing installations;
- versioned UPDATE_NOTES Markdown;
- employee update guide/checklist;
- hashes or validation report.

Markdown alone cannot update JavaScript, CSS, Python or background binaries. It can instruct GPT, but GPT still needs the changed files.

The official update ZIP is the easiest approach:

1. Employee closes ResearchCut and its launcher.
2. Employee extracts the update ZIP.
3. GPT/employee runs APPLY_UPDATE_2.1.ps1 with the current ResearchCut folder as Target.
4. The script creates a timestamped backup of every replaced program file.
5. The script copies the 2.1 payload.
6. It runs syntax and version checks.
7. Employee starts ResearchCut and confirms version 2.1.0.

Local projects are outside the program folder, so program updates do not normally touch project data. A project backup is still recommended before any update.

## GPT update prompt for an employee

Give the employee's GPT the update ZIP and say:

    Close ResearchCut. Read EMPLOYEE_UPDATE_GUIDE.md completely. Locate my current
    ResearchCut Editor folder, apply the included update using APPLY_UPDATE_2.1.ps1,
    preserve all projects/background assets, run the listed checks, restart the app,
    and report the installed version and backup folder. Do not delete old data.

The GPT must not attempt an update from UPDATE_NOTES alone.

