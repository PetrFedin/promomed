DELETE FROM staff_assignments
WHERE id NOT IN (
  SELECT MIN(id)
  FROM staff_assignments
  GROUP BY staff_name,role,venue,shift_start,shift_end
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_assignment_seed_identity
ON staff_assignments(staff_name,role,venue,shift_start,shift_end);
