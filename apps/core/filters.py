"""Shared DRF filter backends."""

from rest_framework.filters import OrderingFilter


class StableOrderingFilter(OrderingFilter):
    """OrderingFilter that guarantees a total order.

    Ordering by a non-unique column -- salary, surname, joined date -- leaves
    tied rows in whatever order the database happens to return. Under
    pagination that is a correctness bug, not a cosmetic one: between two
    requests the same row can appear on page 1 and page 2, or be skipped by
    both, because the tie straddles the page boundary.

    Appending the primary key makes every ordering total, so a page boundary
    can never fall inside an ambiguous run. The cost is one extra sort key,
    which the database resolves only among rows that were already tied.

    Callers that already order by id are left alone.
    """

    tiebreaker = "id"

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            # No ordering from the request or the view: the model's
            # Meta.ordering applies, and that carries its own tiebreaker.
            return ordering

        fields = list(ordering)
        if any(field.lstrip("-") == self.tiebreaker for field in fields):
            return fields
        return fields + [self.tiebreaker]
