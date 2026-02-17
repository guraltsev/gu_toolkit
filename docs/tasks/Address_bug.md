Address the bug:

BUGNAME: 

in `docs\bugs`. 

- Assess the state of completion.

- Treat files in `docs\notebook` as source of truth for whether this bug is still present. If your finding is in contradiction with the behavior documented in the notebook issue a WARNING. NEVER change `docs\notebook` files on your own. 

- Plan remediation.

- If solution is unclear and requires feedback provide necessary information in the form of an additional section in the bug markdown file and request ANSWERS from the user. Provide clear alternatives with rationale Commit and push the changes to the bug description and STOP. Do not implement if correct solution is not clear. 
- If solution is clear implement the solution. Make sure to follow the guidelines in `\docs\develop_guide\develop_guide.md` and `Agents.md`. 

- After implementing the solution make sure there is comprehensive test coverage for this behavior and all code has documentation, docstrings, internal code docs, fully updated. 

- Document changes in the issue md file by adding a checklist of what has been done. Do not close the issue before external review. 