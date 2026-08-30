"""Populate the database with a realistic ACME org.

Thin by design: argument parsing and output only. The generation logic lives
in apps.core.seeding and is tested directly.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.seeding import DEFAULT_SEED, SeedError, seed_employees

DEFAULT_COUNT = 10_000


class Command(BaseCommand):
    help = "Seed the database with deterministic, realistic employee data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help=f"How many employees to create (default: {DEFAULT_COUNT}).",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing employees first. Required to re-seed.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"RNG seed (default: {DEFAULT_SEED}). Same seed, same data.",
        )

    def handle(self, *args, **options):
        try:
            created = seed_employees(
                options["count"],
                seed=options["seed"],
                flush=options["flush"],
            )
        except SeedError as exc:
            raise CommandError(str(exc)) from exc

        if options["verbosity"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {created} employees (seed={options['seed']})."
                )
            )
