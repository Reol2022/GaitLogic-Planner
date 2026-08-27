# MySQL integration test database

Integration tests must use a dedicated database named `gaitlogic_test`. The application database is never an acceptable fallback.

The current application account can connect to MySQL 8.0 but must not be granted server-wide `CREATE DATABASE`. If the database is absent, a database administrator should run the following minimal setup, replacing the account host only when the existing account uses a more restrictive host value:

```sql
CREATE DATABASE `gaitlogic_test`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX,
      REFERENCES, CREATE TEMPORARY TABLES, LOCK TABLES
ON `gaitlogic_test`.*
TO 'gaitlogic_planner'@'%';
```

Configure the test process only:

```powershell
$env:GAITLOGIC_TEST_DATABASE_URL = 'mysql+pymysql://<test-user>:<password>@<host>:3306/gaitlogic_test?charset=utf8mb4'
```

Before any integration test creates tables, it must parse the URL and assert that the database component is exactly `gaitlogic_test`. A missing variable, a different database name, or a URL equal to the application `DATABASE_URL` is a hard stop.

Do not place the test URL or password in committed files, reports, traces, metrics, or test output.
