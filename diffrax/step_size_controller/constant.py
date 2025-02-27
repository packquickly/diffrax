from typing import Callable, Optional, Sequence, Tuple, Union

import equinox.internal as eqxi
import jax.numpy as jnp

from ..custom_types import Array, Int, PyTree, Scalar
from ..solution import RESULTS
from ..term import AbstractTerm
from .base import AbstractStepSizeController


class ConstantStepSize(AbstractStepSizeController):
    """Use a constant step size, equal to the `dt0` argument of
    [`diffrax.diffeqsolve`][].
    """

    def wrap(self, direction: Scalar):
        return self

    def init(
        self,
        terms: PyTree[AbstractTerm],
        t0: Scalar,
        t1: Scalar,
        y0: PyTree,
        dt0: Optional[Scalar],
        args: PyTree,
        func: Callable[[Scalar, PyTree, PyTree], PyTree],
        error_order: Optional[Scalar],
    ) -> Tuple[Scalar, Scalar]:
        del terms, t1, y0, args, func, error_order
        if dt0 is None:
            raise ValueError(
                "Constant step size solvers cannot select step size automatically; "
                "please pass a value for `dt0`."
            )
        return t0 + dt0, dt0

    def adapt_step_size(
        self,
        t0: Scalar,
        t1: Scalar,
        y0: PyTree,
        y1_candidate: PyTree,
        args: PyTree,
        y_error: PyTree,
        error_order: Scalar,
        controller_state: Scalar,
    ) -> Tuple[bool, Scalar, Scalar, bool, Scalar, RESULTS]:
        del t0, y0, y1_candidate, args, y_error, error_order
        return (
            True,
            t1,
            t1 + controller_state,
            False,
            controller_state,
            RESULTS.successful,
        )


class StepTo(AbstractStepSizeController):
    """Make steps to just prespecified times."""

    ts: Union[Sequence[Scalar], Array["times"]]  # noqa: F821

    def __post_init__(self):
        object.__setattr__(self, "ts", jnp.asarray(self.ts))
        if self.ts.ndim != 1:
            raise ValueError("`ts` must be one-dimensional.")
        if len(self.ts) < 2:
            raise ValueError("`ts` must have length at least 2.")

    def wrap(self, direction: Scalar):
        ts = self.ts * direction
        # Only tested after we've set the direction.
        ts = eqxi.error_if(
            ts,
            ts[1:] <= ts[:-1],
            "`StepTo(ts=...)` must be strictly increasing (or strictly decreasing if "
            "t0 > t1).",
        )
        return type(self)(ts=ts)

    def init(
        self,
        terms: PyTree[AbstractTerm],
        t0: Scalar,
        t1: Scalar,
        y0: PyTree,
        dt0: None,
        args: PyTree,
        func: Callable[[Scalar, PyTree, PyTree], PyTree],
        error_order: Optional[Scalar],
    ) -> Tuple[Scalar, int]:
        del y0, args, func, error_order
        if dt0 is not None:
            raise ValueError(
                "`dt0` should be `None`. Step location is already determined "
                f"by {type(self).__name__}(ts=...).",
            )
        ts = eqxi.error_if(
            self.ts,
            (t0 != self.ts[0]) | (t1 != self.ts[-1]),
            "Must have `t0==ts[0]` and `t1==ts[-1]`.",
        )
        return ts[1], 2

    def adapt_step_size(
        self,
        t0: Scalar,
        t1: Scalar,
        y0: Array["state"],  # noqa: F821
        y1_candidate: Array["state"],  # noqa: F821
        args: PyTree,
        y_error: Array["state"],  # noqa: F821
        error_order: Scalar,
        controller_state: int,
    ) -> Tuple[bool, Scalar, Scalar, bool, Int, RESULTS]:
        del t0, y0, y1_candidate, args, y_error, error_order
        return (
            True,
            t1,
            self.ts[controller_state],
            False,
            controller_state + 1,
            RESULTS.successful,
        )


StepTo.__init__.__doc__ = """**Arguments:**

- `ts`: The times to step to. Must be an increasing/decreasing sequence of times
    between the `t0` and `t1` (inclusive) passed to [`diffrax.diffeqsolve`][].
    Correctness of `ts` with respect to `t0` and `t1` as well as its
    monotonicity is checked by the implementation.
"""
