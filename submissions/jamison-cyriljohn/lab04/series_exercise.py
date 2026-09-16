"""
HOW ACCURATE IS GOOD ENOUGH?
Approximating a Civil Engineering Function Using Infinite Series
------------------------------------------------------------------
Progression: Geometric Series -> Power Series -> Maclaurin -> Taylor
             -> Engineering Approximation (y = L sin(theta)) -> Error
             Analysis -> Engineering Decision
"""

import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["figure.dpi"] = 110

# ============================================================
# PART 1: GEOMETRIC SERIES
# ============================================================

def geometric_sum(x, N):
    """S_N = 1 + x + x^2 + ... + x^N  (no closed-form shortcut)"""
    total = 0.0
    for k in range(N + 1):
        total += x ** k
    return total


def part1_geometric():
    print("=" * 70)
    print("PART 1: GEOMETRIC SERIES")
    print("=" * 70)
    rows = []
    for x in [0.5, 0.8, 0.9]:
        exact = 1.0 / (1.0 - x)
        for N in [2, 5, 10, 20, 50]:
            approx = geometric_sum(x, N)
            err = abs(exact - approx)
            rows.append({"x": x, "N terms": N + 1, "Exact 1/(1-x)": exact,
                         "Partial Sum": approx, "Abs Error": err})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v:0.6f}"))
    print("\nObservation: larger x -> slower convergence (ratio x closer to 1\n"
          "means each added term shrinks the remaining error more slowly).\n")
    return df


# ============================================================
# PART 2: POWER SERIES
# ============================================================

def power_series(x, coefficients):
    """Evaluate P_N(x) = sum a_k * x^k for a list of coefficients"""
    result = 0.0
    for k, a_k in enumerate(coefficients):
        result += a_k * (x ** k)
    return result


def part2_power_series():
    print("=" * 70)
    print("PART 2: POWER SERIES (sanity check)")
    print("=" * 70)
    coeffs = [1, -1 / 6, 1 / 120]  # crude odd-only demo, just for the sum tool
    val = power_series(0.5, coeffs)
    print(f"power_series(0.5, {coeffs}) = {val:.6f}\n")


# ============================================================
# PART 3: MACLAURIN SERIES FOR sin(theta)
# ============================================================

def sin_maclaurin(theta, N):
    """Approximate sin(theta) [theta in radians] using N terms of the
    Maclaurin series (terms indexed n = 0..N-1)."""
    result = 0.0
    for n in range(N):
        sign = (-1) ** n
        factorial = math.factorial(2 * n + 1)
        result += sign * (theta ** (2 * n + 1)) / factorial
    return result


def part3_maclaurin():
    print("=" * 70)
    print("PART 3: MACLAURIN SERIES FOR sin(theta), theta = 10 deg")
    print("=" * 70)
    theta_deg = 10
    theta = math.radians(theta_deg)
    exact = math.sin(theta)
    rows = []
    for N in [1, 2, 3, 4]:
        approx = sin_maclaurin(theta, N)
        err = abs(exact - approx)
        pct = err / abs(exact) * 100
        rows.append({"Terms": N, "Approximation": approx, "Exact": exact,
                     "Abs Error": err, "% Error": pct})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v:0.8f}"))
    print()
    return df


# ============================================================
# PART 4: ENGINEERING INVESTIGATION  y = L sin(theta)
# ============================================================

L = 20.0  # m
ANGLES_DEG = [1, 2, 5, 10, 15, 20, 30]
TERMS_LIST = [1, 2, 3, 4]


def part4_engineering_tables():
    print("=" * 70)
    print("PART 4: ENGINEERING TABLES  y = L * sin(theta), L = 20 m")
    print("=" * 70)
    tables = {}
    for N in TERMS_LIST:
        rows = []
        for deg in ANGLES_DEG:
            theta = math.radians(deg)
            y_exact = L * math.sin(theta)
            y_approx = L * sin_maclaurin(theta, N)
            abs_err = abs(y_exact - y_approx)
            pct_err = abs_err / abs(y_exact) * 100 if y_exact != 0 else 0.0
            rows.append({"Angle (deg)": deg, "Exact y (m)": y_exact,
                         "Approx y (m)": y_approx, "Abs Error (m)": abs_err,
                         "% Error": pct_err})
        df = pd.DataFrame(rows)
        tables[N] = df
        print(f"\n-- {N} term(s) --")
        print(df.to_string(index=False, float_format=lambda v: f"{v:0.6f}"))
    print()
    return tables


# ============================================================
# PART 5: TAYLOR SERIES CENTERED AT a = 10 deg
# ============================================================

def sin_taylor(theta, a, N):
    """Approximate sin(theta) [radians] using a Taylor series of N terms
    centered at a [radians]."""
    result = 0.0
    sin_a, cos_a = math.sin(a), math.cos(a)
    for n in range(N):
        derivative_pattern = n % 4
        if derivative_pattern == 0:
            f_deriv = sin_a
        elif derivative_pattern == 1:
            f_deriv = cos_a
        elif derivative_pattern == 2:
            f_deriv = -sin_a
        else:
            f_deriv = -cos_a
        term = f_deriv * ((theta - a) ** n) / math.factorial(n)
        result += term
    return result


def part5_taylor_comparison():
    print("=" * 70)
    print("PART 5: MACLAURIN (a=0) vs TAYLOR (a=10 deg)")
    print("=" * 70)
    a = math.radians(10)
    rows = []
    for deg in ANGLES_DEG:
        theta = math.radians(deg)
        exact = math.sin(theta)
        for N in TERMS_LIST:
            mac = sin_maclaurin(theta, N)
            tay = sin_taylor(theta, a, N)
            rows.append({
                "Angle (deg)": deg, "Terms": N,
                "Maclaurin % Err": abs(exact - mac) / abs(exact) * 100,
                "Taylor(a=10) % Err": abs(exact - tay) / abs(exact) * 100,
            })
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v:0.6f}"))
    print("\nObservation: Taylor centered at 10 deg wins near 10 deg; Maclaurin\n"
          "(centered at 0) wins near 0 deg. Far from its own center, each\n"
          "series degrades.\n")
    return df


# ============================================================
# PART 6: ERROR-TOLERANCE ENGINEERING DECISION (<0.1% error)
# ============================================================

TOLERANCE_PCT = 0.1
MAX_TERMS_SEARCH = 15


def min_terms_for_tolerance(theta, series_func, tol_pct=TOLERANCE_PCT,
                             max_terms=MAX_TERMS_SEARCH):
    exact = math.sin(theta)
    for N in range(1, max_terms + 1):
        approx = series_func(theta, N)
        pct = abs(exact - approx) / abs(exact) * 100 if exact != 0 else 0.0
        if pct < tol_pct:
            return N, pct
    return None, None  # tolerance not reached within max_terms


def part6_tolerance_decision():
    print("=" * 70)
    print(f"PART 6: MIN TERMS FOR < {TOLERANCE_PCT}% ERROR")
    print("=" * 70)
    a = math.radians(10)
    rows = []
    for deg in ANGLES_DEG:
        theta = math.radians(deg)
        n_mac, e_mac = min_terms_for_tolerance(theta, lambda t, N: sin_maclaurin(t, N))
        n_tay, e_tay = min_terms_for_tolerance(theta, lambda t, N: sin_taylor(t, a, N))
        rows.append({"Angle (deg)": deg,
                     "Maclaurin: N needed": n_mac, "Maclaurin % Err": e_mac,
                     "Taylor(a=10): N needed": n_tay, "Taylor % Err": e_tay})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v:0.6f}" if v is not None else "n/a"))

    # Small-angle approximation sin(theta) ~= theta : critical angle
    print("\nSmall-angle test: sin(theta) ~ theta (1-term Maclaurin)")
    critical_angle = None
    for deg in np.arange(1, 45.05, 0.5):
        theta = math.radians(deg)
        approx = theta  # 1-term Maclaurin
        exact = math.sin(theta)
        pct = abs(exact - approx) / abs(exact) * 100
        if pct >= TOLERANCE_PCT and critical_angle is None:
            critical_angle = deg
            break
    print(f"The 1-term approximation sin(theta) ~ theta exceeds "
          f"{TOLERANCE_PCT}% error at approximately theta = {critical_angle:.1f} deg.\n")
    return df, critical_angle


# ============================================================
# PLOTS
# ============================================================

def make_plots(critical_angle):
    a = math.radians(10)
    N_range = list(range(1, 9))

    # --- Plot 1: Convergence plot (% error vs N, for several angles) ---
    fig, ax = plt.subplots(figsize=(7, 5))
    for deg in [5, 10, 20, 30]:
        theta = math.radians(deg)
        exact = math.sin(theta)
        errs = []
        for N in N_range:
            approx = sin_maclaurin(theta, N)
            errs.append(abs(exact - approx) / abs(exact) * 100 + 1e-16)
        ax.semilogy(N_range, errs, marker="o", label=f"{deg} deg")
    ax.axhline(TOLERANCE_PCT, color="red", linestyle="--", linewidth=1,
               label=f"{TOLERANCE_PCT}% tolerance")
    ax.set_xlabel("Number of terms, N")
    ax.set_ylabel("Percentage error (log scale)")
    ax.set_title("Convergence of Maclaurin Approximation for sin(theta)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig("/home/claude/plot1_convergence.png")
    plt.close(fig)

    # --- Plot 2: Function comparison plot ---
    theta_deg_range = np.linspace(-30, 50, 400)
    theta_rad_range = np.radians(theta_deg_range)
    exact_curve = np.sin(theta_rad_range)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for N in [1, 2, 4]:
        mac_curve = [sin_maclaurin(t, N) for t in theta_rad_range]
        axes[0].plot(theta_deg_range, mac_curve, label=f"Maclaurin N={N}")
    axes[0].plot(theta_deg_range, exact_curve, "k--", linewidth=2, label="Exact sin")
    axes[0].set_title("Maclaurin (centered at 0 deg)")
    axes[0].set_xlabel("theta (deg)")
    axes[0].set_ylabel("sin(theta)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    for N in [1, 2, 4]:
        tay_curve = [sin_taylor(t, a, N) for t in theta_rad_range]
        axes[1].plot(theta_deg_range, tay_curve, label=f"Taylor N={N}")
    axes[1].plot(theta_deg_range, exact_curve, "k--", linewidth=2, label="Exact sin")
    axes[1].axvline(10, color="gray", linestyle=":", linewidth=1)
    axes[1].set_title("Taylor (centered at 10 deg)")
    axes[1].set_xlabel("theta (deg)")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    fig.suptitle("Exact sin(theta) vs Series Approximations")
    fig.tight_layout()
    fig.savefig("/home/claude/plot2_function_comparison.png")
    plt.close(fig)

    # --- Plot 3: Error comparison (Maclaurin vs Taylor), abs & pct ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    N_fixed = 2
    abs_mac, abs_tay, pct_mac, pct_tay = [], [], [], []
    for deg in ANGLES_DEG:
        theta = math.radians(deg)
        exact = math.sin(theta)
        mac = sin_maclaurin(theta, N_fixed)
        tay = sin_taylor(theta, a, N_fixed)
        abs_mac.append(abs(exact - mac) * L)
        abs_tay.append(abs(exact - tay) * L)
        pct_mac.append(abs(exact - mac) / abs(exact) * 100)
        pct_tay.append(abs(exact - tay) / abs(exact) * 100)

    width = 0.35
    x_pos = np.arange(len(ANGLES_DEG))
    axes[0].bar(x_pos - width / 2, abs_mac, width, label="Maclaurin")
    axes[0].bar(x_pos + width / 2, abs_tay, width, label="Taylor (a=10)")
    axes[0].set_xticks(x_pos)
    axes[0].set_xticklabels(ANGLES_DEG)
    axes[0].set_xlabel("Angle (deg)")
    axes[0].set_ylabel("Absolute error in y (m)")
    axes[0].set_title(f"Absolute Error in y=L sin(theta), N={N_fixed} terms")
    axes[0].legend()
    axes[0].grid(alpha=0.3, axis="y")

    axes[1].bar(x_pos - width / 2, pct_mac, width, label="Maclaurin")
    axes[1].bar(x_pos + width / 2, pct_tay, width, label="Taylor (a=10)")
    axes[1].axhline(TOLERANCE_PCT, color="red", linestyle="--", linewidth=1,
                     label=f"{TOLERANCE_PCT}% tolerance")
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(ANGLES_DEG)
    axes[1].set_xlabel("Angle (deg)")
    axes[1].set_ylabel("Percentage error (%)")
    axes[1].set_yscale("log")
    axes[1].set_title(f"Percentage Error, N={N_fixed} terms")
    axes[1].legend()
    axes[1].grid(alpha=0.3, axis="y", which="both")

    fig.tight_layout()
    fig.savefig("/home/claude/plot3_error_comparison.png")
    plt.close(fig)

    print("Saved plot1_convergence.png, plot2_function_comparison.png, "
          "plot3_error_comparison.png\n")


# ============================================================
# PART 7: WRITTEN ENGINEERING RECOMMENDATION
# ============================================================

def part7_recommendation(tol_df, critical_angle):
    print("=" * 70)
    print("PART 7: ENGINEERING RECOMMENDATION")
    print("=" * 70)
    text = f"""
Decision: For the surveying/structural calculation y = L*sin(theta), a
Maclaurin series expansion (centered at theta = 0) is recommended for the
typical working range of angles (0-30 deg), EXCEPT where the analysis is
concentrated tightly around a known non-zero angle (e.g. a fixed design
angle of ~10 deg), in which case a Taylor series centered at that angle
is more efficient.

Supporting evidence from the numerical study:
- Terms required: to reach the <{TOLERANCE_PCT}% error requirement, the
  Maclaurin series needs only 1-2 terms for angles below about 10 deg,
  and 2-3 terms out to 30 deg (see Part 6 table below).
- Percentage error achieved: with 3 terms, the Maclaurin error is well
  under {TOLERANCE_PCT}% for every angle tested (1-30 deg).
- Convergence behavior: error decreases rapidly (each additional term
  reduces error by roughly a factor of theta^2), and convergence is
  fastest near the expansion point and slows the farther theta is from it.
- Computational simplicity vs accuracy: a 2-3 term polynomial is far
  cheaper to evaluate than a full trigonometric call in resource-limited
  embedded surveying instruments, at negligible accuracy cost.
- Valid angle range: the plain small-angle approximation sin(theta) ~
  theta (1 term) is only good enough (<{TOLERANCE_PCT}% error) up to about
  {critical_angle:.1f} deg; beyond that, add at least one more term.
- If the working angle is known in advance and stays near a fixed value
  away from zero (e.g. a ramp consistently near 10 deg), centering a
  Taylor series at that value converges even faster near that value,
  though it becomes worse than Maclaurin far from it (see Part 5).
- For safety-critical or highly irregular-angle applications, or where
  simplicity is not a constraint, using the exact math.sin() function is
  always an acceptable and simplest choice — the series methods are
  valuable mainly for insight, verification, and lightweight computation.

Recommendation: use a 3-term Maclaurin series for general-purpose angles
between 0-30 deg (comfortably meets the {TOLERANCE_PCT}% tolerance with
margin), or a 2-term Taylor series centered on the design angle when the
system operates near one specific, known angle.
"""
    print(text)
    return text


# ============================================================
# MAIN
# ============================================================

def main():
    part1_geometric()
    part2_power_series()
    part3_maclaurin()
    part4_engineering_tables()
    part5_taylor_comparison()
    tol_df, critical_angle = part6_tolerance_decision()
    make_plots(critical_angle)
    part7_recommendation(tol_df, critical_angle)


if __name__ == "__main__":
    main()
