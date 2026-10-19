# Local asset library

Uploaded media files are content-addressed in this directory. Catalog metadata lives in `catalog/<asset-id>.json`.

Each asset record stores topic, description, applicable SOP, revision, approval/draft status, source/owner, license/usage rights, technical reviewer, review notes and a SHA-256 checksum. The app requires reviewer, source and license fields to mark a record approved. That is an operator assertion, not independent technical validation.

No real pharmaceutical demonstration is bundled. Example test colors and placeholders are engineering fixtures, not GMP-approved media.

Use a different record for each applicable revision. The library retrieves approved, checksum-matching assets only for the exact SOP number, revision and topic. Semantic matching and validity-date expiration controls remain future work.
