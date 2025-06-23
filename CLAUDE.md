#Bash commands
- pnpm run dev: Run the project in dev mode (recommended)
- pnpm run build: Build a production optimized build

#Code Style: 
- package style modules: every python-specific subfolder should be treated as it's own package module with an __init__.py file
- prefer absolute imports over wildcard imports to keep namespaces clean 

#Workflow
- Do a typecheck when you're done making series of code changges
- Only run single tests, and organize these tests in a /tests folder inside the directory you are in to not clutter main logic

