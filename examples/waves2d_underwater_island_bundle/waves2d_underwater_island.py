from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve


def smoothstep01(z: np.ndarray | float) -> np.ndarray | float:
    z = np.clip(z, 0.0, 1.0)
    return z * z * (3.0 - 2.0 * z)


@dataclass
class Grid2D:
    x: np.ndarray
    y: np.ndarray
    X: np.ndarray
    Y: np.ndarray
    dx: float
    dy: float
    Lx: float
    Ly: float


@dataclass
class Medium:
    depth: np.ndarray
    c2: np.ndarray
    speed: np.ndarray
    sigma: np.ndarray


@dataclass
class TimeSimulation:
    x: np.ndarray
    y: np.ndarray
    depth: np.ndarray
    sigma: np.ndarray
    snapshots: np.ndarray
    times: np.ndarray
    omega: float
    dt: float
    note: str = ""


@dataclass
class FrequencySolution:
    x: np.ndarray
    y: np.ndarray
    depth: np.ndarray
    sigma: np.ndarray
    omega: float
    U: np.ndarray
    incident: np.ndarray
    total: np.ndarray


def make_grid(
    nx: int = 181,
    ny: int = 121,
    Lx: float = 12.0,
    Ly: float = 7.0,
) -> Grid2D:
    x = np.linspace(-Lx, Lx, nx)
    y = np.linspace(-Ly, Ly, ny)
    X, Y = np.meshgrid(x, y, indexing="xy")
    dx = float(x[1] - x[0])
    dy = float(y[1] - y[0])
    return Grid2D(x=x, y=y, X=X, Y=Y, dx=dx, dy=dy, Lx=Lx, Ly=Ly)


def underwater_island_depth(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    deep_depth: float = 1.0,
    island_center: tuple[float, float] = (2.0, 0.0),
    island_height: float = 0.62,
    radius_x: float = 1.7,
    radius_y: float = 1.9,
    shelf_strength: float = 0.0,
    shelf_x0: float = 5.0,
    min_depth: float = 0.22,
) -> np.ndarray:
    """
    Depth profile H(x,y) for a submerged island.

    The island is encoded as a Gaussian bump in the sea floor,
    which means the water becomes shallower near its center.
    """
    xc, yc = island_center
    mound = island_height * np.exp(-((X - xc) / radius_x) ** 2 - ((Y - yc) / radius_y) ** 2)
    shelf = shelf_strength / (1.0 + np.exp(-(X - shelf_x0) / 0.8))
    depth = deep_depth - mound - shelf
    return np.clip(depth, min_depth, None)


def make_sponge(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    Lx: float,
    Ly: float,
    width_x: float = 2.2,
    width_y: float = 1.5,
    strength: float = 1.2,
    left_strength: float = 0.9,
) -> np.ndarray:
    """Smooth absorbing layer near the edges."""
    sx_left = smoothstep01((X - (-Lx + 0.4)) / width_x)
    sx_left = 1.0 - sx_left
    sx_right = smoothstep01((X - (Lx - width_x)) / width_x)
    sy_top = smoothstep01((Y - (Ly - width_y)) / width_y)
    sy_bottom = 1.0 - smoothstep01((Y - (-Ly + 0.3)) / width_y)
    sigma = left_strength * sx_left**2 + strength * sx_right**2 + 0.8 * strength * sy_top**2 + 0.8 * strength * sy_bottom**2
    return sigma


def make_medium(
    grid: Grid2D,
    *,
    gravity: float = 1.0,
    deep_depth: float = 1.0,
    island_center: tuple[float, float] = (2.0, 0.0),
    island_height: float = 0.62,
    radius_x: float = 1.7,
    radius_y: float = 1.9,
    shelf_strength: float = 0.0,
    min_depth: float = 0.22,
    sponge_strength: float = 1.2,
) -> Medium:
    depth = underwater_island_depth(
        grid.X,
        grid.Y,
        deep_depth=deep_depth,
        island_center=island_center,
        island_height=island_height,
        radius_x=radius_x,
        radius_y=radius_y,
        shelf_strength=shelf_strength,
        min_depth=min_depth,
    )
    c2 = gravity * depth
    speed = np.sqrt(c2)
    sigma = make_sponge(grid.X, grid.Y, Lx=grid.Lx, Ly=grid.Ly, strength=sponge_strength)
    return Medium(depth=depth, c2=c2, speed=speed, sigma=sigma)


def plane_wave_source_shape(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    x0: float,
    width: float = 0.38,
    y_margin: float = 0.9,
    amplitude: float = 1.0,
    Ly: float | None = None,
) -> np.ndarray:
    """Tall narrow strip used as an approximate plane-wave emitter."""
    if Ly is None:
        Ly = float(np.max(np.abs(Y)))
    strip = np.exp(-((X - x0) / width) ** 2)
    y_window = smoothstep01((Y + Ly - y_margin) / y_margin) * (1.0 - smoothstep01((Y - (Ly - y_margin)) / y_margin))
    return amplitude * strip * y_window


def estimate_stable_dt(c2: np.ndarray, dx: float, dy: float, cfl: float = 0.45) -> float:
    cmax = float(np.sqrt(np.max(c2)))
    return cfl / (cmax * np.sqrt(1.0 / dx**2 + 1.0 / dy**2))


def divergence_form_operator(u: np.ndarray, c2: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Compute div(c^2 grad u) with homogeneous Neumann closure."""
    u_w = np.pad(u, ((0, 0), (1, 0)), mode="edge")[:, :-1]
    u_e = np.pad(u, ((0, 0), (0, 1)), mode="edge")[:, 1:]
    u_s = np.pad(u, ((1, 0), (0, 0)), mode="edge")[:-1, :]
    u_n = np.pad(u, ((0, 1), (0, 0)), mode="edge")[1:, :]

    c2_w = 0.5 * (c2 + np.pad(c2, ((0, 0), (1, 0)), mode="edge")[:, :-1])
    c2_e = 0.5 * (c2 + np.pad(c2, ((0, 0), (0, 1)), mode="edge")[:, 1:])
    c2_s = 0.5 * (c2 + np.pad(c2, ((1, 0), (0, 0)), mode="edge")[:-1, :])
    c2_n = 0.5 * (c2 + np.pad(c2, ((0, 1), (0, 0)), mode="edge")[1:, :])

    return (
        (c2_e * (u_e - u) - c2_w * (u - u_w)) / dx**2
        + (c2_n * (u_n - u) - c2_s * (u - u_s)) / dy**2
    )


def run_time_domain(
    grid: Grid2D,
    medium: Medium,
    *,
    omega: float = 1.9,
    source_x0: float | None = None,
    source_amplitude: float = 0.9,
    source_width: float = 0.42,
    ramp_time: float = 5.0,
    total_time: float = 30.0,
    snapshot_stride: int = 4,
    dt: float | None = None,
) -> TimeSimulation:
    if dt is None:
        dt = estimate_stable_dt(medium.c2, grid.dx, grid.dy)
    if source_x0 is None:
        source_x0 = -grid.Lx + 1.3

    nsteps = int(np.ceil(total_time / dt))
    ramp_steps = max(1, int(np.ceil(ramp_time / dt)))
    source_shape = plane_wave_source_shape(
        grid.X,
        grid.Y,
        x0=source_x0,
        width=source_width,
        amplitude=source_amplitude,
        Ly=grid.Ly,
    )

    u_prev = np.zeros_like(medium.c2)
    u_curr = np.zeros_like(medium.c2)
    sigma = medium.sigma

    a = 1.0 + 0.5 * sigma * dt
    b = 1.0 - 0.5 * sigma * dt

    snapshots = []
    times = []

    for n in range(nsteps):
        t = n * dt
        ramp = smoothstep01(n / ramp_steps)
        forcing = ramp * np.sin(omega * t) * source_shape
        Lu = divergence_form_operator(u_curr, medium.c2, grid.dx, grid.dy)
        u_next = (2.0 * u_curr - b * u_prev + dt**2 * (Lu + forcing)) / a
        # Nudge the outermost grid lines toward zero inside the sponge.
        u_next[:, 0] *= 0.4
        u_next[:, -1] *= 0.4
        u_next[0, :] *= 0.4
        u_next[-1, :] *= 0.4
        if n % snapshot_stride == 0:
            snapshots.append(u_curr.copy())
            times.append(t)
        u_prev, u_curr = u_curr, u_next

    return TimeSimulation(
        x=grid.x,
        y=grid.y,
        depth=medium.depth,
        sigma=medium.sigma,
        snapshots=np.asarray(snapshots),
        times=np.asarray(times),
        omega=omega,
        dt=dt,
        note="Damped explicit scheme with a strip source approximating a plane wave.",
    )


def _flat_index(i: int, j: int, nx: int) -> int:
    return j * nx + i


def build_divergence_matrix(c2: np.ndarray, dx: float, dy: float) -> sparse.csr_matrix:
    ny, nx = c2.shape
    rows: list[int] = []
    cols: list[int] = []
    data: list[complex] = []

    for j in range(ny):
        for i in range(nx):
            p = _flat_index(i, j, nx)
            center = 0.0

            cW = 0.5 * (c2[j, i] + c2[j, i - 1]) if i > 0 else c2[j, i]
            cE = 0.5 * (c2[j, i] + c2[j, i + 1]) if i < nx - 1 else c2[j, i]
            cS = 0.5 * (c2[j, i] + c2[j - 1, i]) if j > 0 else c2[j, i]
            cN = 0.5 * (c2[j, i] + c2[j + 1, i]) if j < ny - 1 else c2[j, i]

            if i > 0:
                rows.append(p)
                cols.append(_flat_index(i - 1, j, nx))
                data.append(cW / dx**2)
                center -= cW / dx**2
            if i < nx - 1:
                rows.append(p)
                cols.append(_flat_index(i + 1, j, nx))
                data.append(cE / dx**2)
                center -= cE / dx**2
            if j > 0:
                rows.append(p)
                cols.append(_flat_index(i, j - 1, nx))
                data.append(cS / dy**2)
                center -= cS / dy**2
            if j < ny - 1:
                rows.append(p)
                cols.append(_flat_index(i, j + 1, nx))
                data.append(cN / dy**2)
                center -= cN / dy**2

            rows.append(p)
            cols.append(p)
            data.append(center)

    return sparse.csr_matrix((np.asarray(data), (np.asarray(rows), np.asarray(cols))), shape=(nx * ny, nx * ny))


def smooth_cutoff_left(x: np.ndarray, *, transition_center: float, transition_width: float) -> np.ndarray:
    z = (x - (transition_center - transition_width)) / (2.0 * transition_width)
    return 1.0 - smoothstep01(z)


def incident_plane_wave(
    grid: Grid2D,
    *,
    omega: float,
    c_ref: float,
    transition_center: float = -1.5,
    transition_width: float = 2.0,
) -> np.ndarray:
    k = omega / c_ref
    chi = smooth_cutoff_left(grid.x, transition_center=transition_center, transition_width=transition_width)
    phase = np.exp(1j * k * grid.x)
    inc_x = chi * phase
    return np.tile(inc_x[None, :], (grid.y.size, 1))


def helmholtz_operator(
    L: sparse.csr_matrix,
    sigma: np.ndarray,
    omega: float,
) -> sparse.csr_matrix:
    diag = sparse.diags((omega**2 + 1j * omega * sigma).reshape(-1))
    return (L + diag).tocsr()


def solve_steady_state(
    grid: Grid2D,
    medium: Medium,
    *,
    omega: float,
    L: sparse.csr_matrix | None = None,
    source_x0: float | None = None,
    source_amplitude: float = 1.0,
    source_width: float = 0.38,
    background_c2: np.ndarray | None = None,
) -> FrequencySolution:
    """Solve the driven time-harmonic problem and split it into incident + scattered parts.

    The incident field is computed in a flat-bottom background medium driven by the same source strip.
    The scattered field is then recovered from the contrast identity

        A_total (u_total - u_inc) = -(A_total - A_bg) u_inc.

    This is a simple frequency-domain analogue of sending in a wave from the left and watching
    the island perturb it.
    """
    if source_x0 is None:
        source_x0 = -grid.Lx + 1.3
    if L is None:
        L = build_divergence_matrix(medium.c2, grid.dx, grid.dy)
    if background_c2 is None:
        background_c2 = np.full_like(medium.c2, np.max(medium.c2))

    L_bg = build_divergence_matrix(background_c2, grid.dx, grid.dy)
    A_total = helmholtz_operator(L, medium.sigma, omega)
    A_bg = helmholtz_operator(L_bg, medium.sigma, omega)

    source = plane_wave_source_shape(
        grid.X,
        grid.Y,
        x0=source_x0,
        width=source_width,
        amplitude=source_amplitude,
        Ly=grid.Ly,
    )
    rhs = -source.reshape(-1)

    inc_vec = spsolve(A_bg, rhs)
    contrast_rhs = -((A_total - A_bg) @ inc_vec)
    scatter = spsolve(A_total, contrast_rhs)
    total = inc_vec + scatter
    return FrequencySolution(
        x=grid.x,
        y=grid.y,
        depth=medium.depth,
        sigma=medium.sigma,
        omega=omega,
        U=scatter.reshape(medium.depth.shape),
        incident=inc_vec.reshape(medium.depth.shape),
        total=total.reshape(medium.depth.shape),
    )


def downstream_profile(solution: FrequencySolution, *, x_probe: float) -> tuple[np.ndarray, np.ndarray]:
    idx = int(np.argmin(np.abs(solution.x - x_probe)))
    return solution.y, np.abs(solution.total[:, idx])


def save_time_animation(
    sim: TimeSimulation,
    filepath: str | Path,
    *,
    fps: int = 15,
    dpi: int = 120,
    every: int = 1,
    title: str | None = None,
):
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter, FFMpegWriter

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = sim.snapshots[::every]
    times = sim.times[::every]
    extent = [sim.x.min(), sim.x.max(), sim.y.min(), sim.y.max()]
    vmax = np.quantile(np.abs(data), 0.995)
    vmax = float(max(vmax, 0.12))

    fig, ax = plt.subplots(figsize=(8.5, 4.9), constrained_layout=True)
    im = ax.imshow(data[0], extent=extent, origin="lower", cmap="RdBu_r", vmin=-vmax, vmax=vmax, animated=True)
    cs = ax.contour(sim.x, sim.y, sim.depth, levels=np.linspace(sim.depth.min(), sim.depth.max(), 7), colors="k", linewidths=0.45, alpha=0.35)
    text = ax.text(0.02, 0.96, "", transform=ax.transAxes, ha="left", va="top", fontsize=11, bbox=dict(boxstyle="round", facecolor="white", alpha=0.75, edgecolor="none"))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(title or f"Incoming wavetrain scattering from an underwater island (omega={sim.omega:.2f})")
    cbar = fig.colorbar(im, ax=ax, shrink=0.9)
    cbar.set_label("surface displacement eta")

    def update(frame: int):
        im.set_array(data[frame])
        text.set_text(f"t = {times[frame]:.2f}")
        return [im, text]

    anim = FuncAnimation(fig, update, frames=len(data), interval=1000 / fps, blit=True)
    writer = FFMpegWriter(fps=fps, codec="libx264") if filepath.suffix.lower() == ".mp4" else PillowWriter(fps=fps)
    anim.save(filepath, writer=writer, dpi=dpi)
    plt.close(fig)
    return filepath


def save_frequency_cycle_animation(
    solutions: Sequence[FrequencySolution],
    filepath: str | Path,
    *,
    nphase: int = 36,
    fps: int = 12,
    dpi: int = 120,
    title: str = "Steady states for different incoming frequencies",
):
    import matplotlib.pyplot as plt
    from matplotlib.animation import PillowWriter, FFMpegWriter

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    extent = [solutions[0].x.min(), solutions[0].x.max(), solutions[0].y.min(), solutions[0].y.max()]
    vmax = max(float(np.quantile(np.abs(sol.total), 0.995)) for sol in solutions)
    vmax = float(max(vmax, 0.12))
    phases = np.linspace(0.0, 2.0 * np.pi, nphase, endpoint=False)

    n = len(solutions)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(9.6, 6.8), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()

    ims = []
    labels = []
    for ax, sol in zip(axes, solutions):
        frame0 = np.real(sol.total)
        im = ax.imshow(frame0, extent=extent, origin="lower", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax.contour(sol.x, sol.y, sol.depth, levels=np.linspace(sol.depth.min(), sol.depth.max(), 7), colors="k", linewidths=0.45, alpha=0.35)
        ax.set_title(f"omega = {sol.omega:.2f}")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ims.append(im)
        labels.append(ax.text(0.03, 0.96, "phase = 0.00 turns", transform=ax.transAxes, ha="left", va="top", fontsize=10, bbox=dict(boxstyle="round", facecolor="white", alpha=0.75, edgecolor="none")))
    for ax in axes[len(solutions):]:
        ax.axis("off")

    fig.suptitle(title)
    cbar = fig.colorbar(ims[0], ax=axes[: len(solutions)], shrink=0.88, location="right")
    cbar.set_label("Re(U e^{-i phi})")

    writer = FFMpegWriter(fps=fps, codec="libx264") if filepath.suffix.lower() == ".mp4" else PillowWriter(fps=fps)
    with writer.saving(fig, filepath, dpi=dpi):
        for phi in phases:
            for im, label, sol in zip(ims, labels, solutions):
                im.set_data(np.real(sol.total * np.exp(-1j * phi)))
                label.set_text(f"phase = {phi / (2.0 * np.pi):.2f} turns")
            writer.grab_frame()
    plt.close(fig)
    return filepath
