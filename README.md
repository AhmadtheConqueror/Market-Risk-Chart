# Daily Oil Trading Risk Dashboard

Small dashboard for viewing oil market risk, macro/geopolitical risk, company exposure, news, actions, and the overall risk gauge.

## How To Run

1. Open a terminal in this folder.
2. Run:

```bash
npm start
```

3. Open:

```text
http://localhost:3000
```

Admin login:

```text
Username: admin
Password: Password123
```

## Main Files

- `server.js` runs the local backend, login, Excel upload, and saved editable dashboard content.
- `public/index.html` is the page structure shown in the browser.
- `public/style.css` controls the dashboard layout and visual design.
- `public/dashboard.js` controls page behavior, admin mode, refresh, editable sections, and rendering.
- `public/excel.js` reads and maps Excel workbook data.
- `public/risk-engine.js` calculates dashboard risk values from the loaded data.
- `public/charts.js` draws the dashboard charts and gauges.
- `public/data.js` contains fallback/demo dashboard data.
- `database/dashboard.db` stores uploaded data and admin-edited content.
- `uploads/active-market-data.xlsx` is the current uploaded Excel file.

## Simple Idea

The backend loads/saves data. The frontend displays it. Excel data feeds the dashboard, and admin mode controls editing.
