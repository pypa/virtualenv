Use the checked metadata path when replacing seed packages. Install packages one at a time within each seeder process so
its own workers cannot redirect each other's cleanup.
