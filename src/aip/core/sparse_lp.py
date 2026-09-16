"""Optional SciPy/HiGHS sparse LP backend; not an equilibrium certifier."""

from aip.core.sequence_form import SparseMatrix


def solve_sparse_plans(form, *, time_limit):
    try:
        import numpy as np
        from scipy.optimize import linprog
        from scipy.sparse import coo_matrix, csr_matrix, hstack
    except ImportError as error:
        raise RuntimeError("install aip-puzzles[sparse-lp] to use scipy_highs") from error

    def matrix(value):
        if isinstance(value, SparseMatrix):
            rows, cols, data = [], [], []
            for i, j, v in value.entries:
                rows.append(i)
                cols.append(j)
                data.append(v)
            return coo_matrix((data, (rows, cols)), shape=value.shape).tocsr()
        return csr_matrix(value)

    payoff = matrix(form.payoff_matrix)
    flow = tuple(map(matrix, form.flow_matrices))
    values, plans = [], []
    residual = 0.0
    for p in (0, 1):
        a = payoff if p == 0 else -payoff.T
        e, f = flow[p], flow[1-p]
        n, m = a.shape[0], f.shape[0]
        # x >= 0; dual v free. Max f_rhs*v subject to F.T*v <= A.T*x.
        objective = np.concatenate((np.zeros(n), -np.array(form.flow_rhs[1-p])))
        result = linprog(
            objective, A_ub=hstack((-a.T, f.T), format="csr"),
            b_ub=np.zeros(a.shape[1]),
            A_eq=hstack((e, csr_matrix((e.shape[0], m))), format="csr"),
            b_eq=form.flow_rhs[p], bounds=[(0, None)]*n + [(None, None)]*m,
            method="highs", options={"time_limit": time_limit},
        )
        if not result.success:
            raise ValueError(f"sparse LP failed (status {result.status}): {result.message}")
        plan = np.maximum(0, result.x[:n])
        residual = max(residual, float(np.max(np.abs(e @ plan - form.flow_rhs[p]))))
        values.append(float(-result.fun))
        plans.append(tuple(map(float, plan)))
    return values, plans, residual
