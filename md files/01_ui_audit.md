You are a senior developer auditing a junior developer’s FastAPI + Jinja2 project.

Your task is to scan the entire codebase and produce a structured UI/UX audit.

Focus ONLY on:
- HTML templates
- CSS files
- Layout structure
- Navigation
- Forms

Output the following:

1. List of all UI-related files grouped by type:
   - Templates (Jinja/HTML)
   - Stylesheets
   - Static assets

2. Identify:
   - Duplicate layouts
   - Inconsistent styling patterns
   - Missing base template usage (if applicable)
   - Navigation structure issues
   - Form usability issues

3. Identify the MAIN USER FLOW (most important functionality)

4. Identify:
   - Broken or incomplete UI sections
   - Features that should be hidden for MVP

5. DO NOT suggest code yet
6. DO NOT modify any files

Be concise but structured.