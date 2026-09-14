"""Read-only integrity and numerical replay of a published chronological walk.

Replay uses archived shocks, never a random generator. Optional recalibration
also checks the saved coefficients against their causal rolling histories.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import numpy as np

if __package__:
    from .workflow import repository_path
    from .recursive import _calibrate
else:
    from workflow import repository_path
    from recursive import _calibrate


FAMILIES = ('rate', 'sigma', 'xi')
MATRICES = ('factor_covariance', 'raw_correlation', 'correlation', 'cholesky', 'brownian_covariance')
MAX_NPZ_BYTES = 512 * 1024 * 1024


def _fail(message):
    raise ValueError(message)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _loads(text):
    return json.loads(text, object_pairs_hook=_pairs,
                      parse_constant=lambda value: _fail('nonfinite JSON number: ' + value))


def _json(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        _fail('JSON manifest exceeds 8 MiB: ' + path.name)
    value = _loads(path.read_text())
    if not isinstance(value, dict):
        _fail('manifest must be a JSON object: ' + path.name)
    return value


def _path(base, name, directory=False):
    if (not isinstance(name, str) or not name or '\\' in name
            or any(ord(character) < 32 for character in name)):
        _fail('artifact path must be a nonempty relative POSIX path')
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or str(relative) != name or name == '.':
        _fail('artifact path must stay inside its archive: ' + name)
    target = (base / name).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        _fail('artifact symlink escapes its archive: ' + name)
    if not (target.is_dir() if directory else target.is_file()):
        _fail('missing artifact: ' + name)
    return target


def _hash(path, expected):
    if not isinstance(expected, str) or re.fullmatch('[0-9a-f]{64}', expected) is None:
        _fail('invalid SHA256 for ' + path.name)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        _fail('SHA256 mismatch: ' + path.name)


def _files(base, mapping, mandatory):
    if not isinstance(mapping, dict) or not set(mandatory).issubset(mapping):
        _fail('missing required artifact hashes: ' + ', '.join(mandatory))
    for name, expected in mapping.items():
        _hash(_path(base, name), expected)
    return len(mapping)


def _npz(path, required):
    # No extraction and no pickle. Bound decompressed storage before loading.
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != len(required):
            _fail('NPZ contains missing or unexpected arrays: ' + path.name)
        if len({item.filename for item in members}) != len(members):
            _fail('duplicate NPZ members: ' + path.name)
        if sum(item.file_size for item in members) > MAX_NPZ_BYTES:
            _fail('NPZ exceeds the 512 MiB decoded-array bound: ' + path.name)
        declared_bytes = 0
        for item in members:
            if not item.filename.endswith('.npy') or '/' in item.filename or '\\' in item.filename:
                _fail('NPZ members must be named numeric/string arrays')
            with archive.open(item) as stream:
                version = np.lib.format.read_magic(stream)
                reader = {(1, 0): np.lib.format.read_array_header_1_0,
                          (2, 0): np.lib.format.read_array_header_2_0}.get(version)
                if reader is None:
                    _fail('unsupported NPY header version')
                shape, _, dtype = reader(stream, max_header_size=64 * 1024)
                if dtype.hasobject:
                    _fail('object/pickle arrays are forbidden')
                if dtype.itemsize <= 0:
                    _fail('zero-itemsize array dtypes are forbidden')
                elements = 1
                for dimension in shape:
                    if not isinstance(dimension, int) or dimension < 0:
                        _fail('invalid declared array shape')
                    elements *= dimension
                required_bytes = elements * dtype.itemsize
                declared_bytes += required_bytes
                if declared_bytes > MAX_NPZ_BYTES:
                    _fail('declared NPZ array allocation exceeds 512 MiB')
                if required_bytes != item.file_size - stream.tell():
                    _fail('declared NPY shape does not match its stored payload')
    with np.load(path, allow_pickle=False) as archive:
        if set(required) != set(archive.files):
            _fail('missing or unexpected arrays in ' + path.name)
        return {name: archive[name].copy() for name in required}


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(name + ' must be a finite numeric scalar')
    if not np.isfinite(value) or (value <= 0 if positive else value < 0):
        _fail(name + ' must be finite and ' + ('positive' if positive else 'nonnegative'))
    return float(value)


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(name + ' must be an integer at least ' + str(minimum))
    return value


def _array(value, shape, name, nonnegative=False):
    array = np.asarray(value)
    if array.dtype.kind not in 'iuf' or array.shape != shape or not np.isfinite(array).all():
        _fail(name + ' must be finite numeric values with shape ' + str(shape))
    if nonnegative and (array < 0).any():
        _fail(name + ' must be nonnegative')
    return array.astype(float, copy=False)


def _same(actual, expected, name, cancellation_scale=None):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if (actual.dtype.kind not in 'iuf' or expected.dtype.kind not in 'iuf'
            or actual.shape != expected.shape
            or not np.isfinite(actual).all() or not np.isfinite(expected).all()):
        _fail(name + ' shape or finiteness mismatch')
    scale = max(float(np.max(np.abs(expected))) if expected.size else 0., np.finfo(float).tiny)
    if cancellation_scale is not None:
        scale = max(scale, cancellation_scale)
    if not np.allclose(actual, expected, rtol=2e-10, atol=128 * np.finfo(float).eps * scale):
        _fail(name + ' does not match numerical replay')


def _labels(actual, expected, name):
    array = np.asarray(actual)
    if array.dtype.kind not in 'US' or array.shape != (len(expected),) or array.tolist() != list(expected):
        _fail(name + ' labels do not match the declared state order')


def _schema(manifest, version, name):
    if manifest.get('schema_version') != version or isinstance(manifest.get('schema_version'), bool):
        _fail(name + ' has an unsupported schema version')
    if manifest.get('status') != 'complete':
        _fail(name + ' is not complete')


def _rng_state(value, name):
    # Validate checkpoint structure only. Drawing again would not be replay of
    # the archived realized increments and is intentionally outside this tool.
    if not isinstance(value, dict) or value.get('bit_generator') != 'PCG64':
        _fail(name + ' must be a PCG64 checkpoint')
    inner = value.get('state')
    if not isinstance(inner, dict):
        _fail(name + ' has no generator state')
    for key in ('state', 'inc'):
        number = _integer(inner.get(key), name + '.' + key)
        if number >= 2**128:
            _fail(name + ' state is outside uint128')
    if inner['inc'] % 2 != 1:
        _fail(name + ' increment must be odd')
    if value.get('has_uint32') not in (0, 1) or isinstance(value.get('has_uint32'), bool):
        _fail(name + ' has invalid uint32 state')
    if _integer(value.get('uinteger'), name + '.uinteger') >= 2**32:
        _fail(name + ' cached value is outside uint32')


def _audit_equal(actual, expected, name):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            _fail(name + ' audit fields differ')
        for key in expected:
            if key == 'nll_cost':
                # A likelihood cost subtracts two large NLLs. Its roundoff
                # scale is that of the operands, even when the cost is zero.
                scale = max(1., abs(actual.get('raw_nll', 0.)), abs(expected.get('raw_nll', 0.)))
                _same(actual[key], expected[key], name + '.' + key, cancellation_scale=scale)
            else:
                _audit_equal(actual[key], expected[key], name + '.' + key)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            _fail(name + ' audit list differs')
        for index, (a, b) in enumerate(zip(actual, expected)):
            _audit_equal(a, b, name + '[%d]' % index)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            _fail(name + ' audit numeric type differs')
        _same(actual, expected, name)
    elif type(actual) is not type(expected) or actual != expected:
        _fail(name + ' audit value differs')


def _trajectory_csv(path, states, elapsed, maturities):
    with path.open(newline='') as stream:
        rows = csv.reader(stream)
        if next(rows, None) != ['step', 'elapsed_years', 'state', 'maturity', 'value']:
            _fail('trajectory.csv has an invalid header')
        for step, state in enumerate(states):
            for family, name in enumerate(FAMILIES):
                for column, maturity in enumerate(maturities):
                    row = next(rows, None)
                    if row is None or len(row) != 5 or row[0] != str(step) or row[2] != name:
                        _fail('trajectory.csv rows differ from the reported states')
                    _same(float(row[1]), elapsed[step], 'trajectory.csv time')
                    _same(float(row[3]), maturity, 'trajectory.csv maturity')
                    _same(float(row[4]), state[family, column], 'trajectory.csv value')
        if next(rows, None) is not None:
            _fail('trajectory.csv contains extra rows')


def verify_walk(input_dir, recalibrate=False):
    """Verify every archived increment without generating or writing any data."""
    directory = repository_path(input_dir)
    if not directory.is_dir():
        _fail('input must be an existing walk directory')
    manifest = _json(_path(directory, 'manifest.json'))
    _schema(manifest, 2, 'walk manifest')
    checked_hashes = _files(directory, manifest.get('files_sha256'),
                           ('initial_history.npz', 'yield_parameters.csv',
                            'parameter_dynamics.csv', 'transition_intervals.csv'))
    settings = manifest.get('settings')
    if not isinstance(settings, dict):
        _fail('walk settings are missing')
    steps = _integer(settings.get('steps_per_year'), 'steps_per_year', 1)
    substeps = _integer(settings.get('substeps'), 'substeps', 1)
    years = _integer(settings.get('years'), 'years', 1)
    dt = _number(settings.get('dt'), 'dt', positive=True)
    alpha = _number(settings.get('correlation_regularization'), 'correlation_regularization')
    if alpha > 1 or steps * substeps > 1_000_000 or years > 1000:
        _fail('invalid regularization or walk dimensions')
    _same(steps * dt, 1., 'annual duration')
    delta, per_year = dt / substeps, steps * substeps
    budget = _number(settings.get('nll_budget'), 'nll_budget')
    fallback = _number(settings.get('fallback_theta'), 'fallback_theta', positive=True)
    entries = manifest.get('years')
    if not isinstance(entries, list) or len(entries) != years:
        _fail('year inventory does not match requested years')
    _labels(manifest.get('state_names'), FAMILIES, 'manifest states')
    initial = _npz(_path(directory, 'initial_history.npz'),
                   ('history', 'history_dt', 'maturities', 'state_names', 'dates'))
    maturities = np.asarray(initial['maturities'])
    if (maturities.ndim != 1 or not len(maturities) or maturities.dtype.kind not in 'iuf'
            or not np.isfinite(maturities).all() or (maturities <= 0).any()
            or len(np.unique(maturities)) != len(maturities)):
        _fail('initial maturities must be distinct positive numeric values')
    d = len(maturities)
    maturity_names = [str(int(value)) if float(value).is_integer() else str(value) for value in maturities]
    required_exports = (['RAW/DGS' + name + '_with_parameters.csv' for name in maturity_names]
                        + ['CURVE/' + name + '_curve.csv' for name in ('mu', 'theta', 'sigma')])
    missing_exports = sorted(set(required_exports) - set(manifest['files_sha256']))
    if missing_exports:
        _fail('missing required artifact hashes: ' + ', '.join(missing_exports))
    configured = settings.get('maturities')
    if (not isinstance(configured, list) or len(configured) != d
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in configured)
            or not np.isfinite(configured).all() or any(value <= 0 for value in configured)
            or len(set(configured)) != d):
        _fail('configured maturities must be distinct positive numeric values')
    # The workflow sorts columns before storing its state tensors, regardless
    # of the ordering used in the user's command-line maturity selection.
    _same(sorted(configured), maturities, 'configured maturities')
    h = np.asarray(initial['history'])
    if h.ndim != 3 or h.shape[0] < 4:
        _fail('initial history must contain at least four rows')
    h = _array(h, (h.shape[0], 3, d), 'initial history', True).copy()
    clock = _array(initial['history_dt'], (len(h) - 1,), 'initial history clock', True).copy()
    if (clock <= 0).any():
        _fail('initial history clock must be strictly positive')
    _labels(initial['state_names'], FAMILIES, 'initial states')
    dates = initial['dates']
    if (dates.shape != (len(h),) or dates.dtype.kind not in 'US'
            or any(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) is None for date in dates.tolist())):
        _fail('initial dates must be one ISO date per history row')
    try:
        parsed_dates = dates.astype('datetime64[D]')
    except ValueError as error:
        raise ValueError('initial dates are invalid') from error
    if np.isnat(parsed_dates).any() or not (np.diff(parsed_dates).astype(int) > 0).all():
        _fail('initial dates must increase strictly')
    if manifest.get('walk_history_rows') != len(h) or settings.get('history_window') != len(h):
        _fail('walk history row count differs from its manifest')
    if manifest.get('walk_history_start') != dates[0] or manifest.get('forecast_origin') != dates[-1]:
        _fail('initial history date endpoints differ from the manifest')
    basis = settings.get('time_basis')
    if basis == 'observation':
        expected_clock = np.full(len(h) - 1, dt)
    elif basis == 'act365f':
        expected_clock = np.diff(parsed_dates).astype(float) / 365.
    else:
        _fail('unsupported historical time basis')
    _same(clock, expected_clock, 'initial history time convention')
    priors = None
    previous_rng = None
    total_increments = total_projections = 0
    used_years = set()
    for year, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get('year') != year + 1:
            _fail('years must appear once in consecutive order')
        year_dir = _path(directory, entry.get('directory'), directory=True)
        if year_dir in used_years:
            _fail('duplicate year directory')
        used_years.add(year_dir)
        year_manifest_path = _path(year_dir, 'manifest.json')
        _hash(year_manifest_path, entry.get('manifest_sha256'))
        checked_hashes += 1
        year_manifest = _json(year_manifest_path)
        _schema(year_manifest, 2, 'year manifest')
        if year_manifest.get('year') != year + 1:
            _fail('year manifest number mismatch')
        _same(year_manifest.get('elapsed_start_years'), year, 'year start')
        _same(year_manifest.get('elapsed_end_years'), year + 1, 'year end')
        if year_manifest.get('covariance_elapsed_time') != 'relative to this year start':
            _fail('unsupported covariance clock convention')
        checked_hashes += _files(year_dir, year_manifest.get('files_sha256'),
                                ('trajectory.npz', 'trajectory.csv', 'restart.npz', 'covariance/manifest.json'))
        diagnostics = year_manifest.get('diagnostics')
        if not isinstance(diagnostics, dict):
            _fail('missing year diagnostics')
        if year_manifest.get('rng_state_before') != previous_rng:
            _fail('year RNG checkpoint does not continue the prior year')
        if priors is None:
            if year_manifest.get('prior_thetas_before') is not None:
                _fail('first year must not invent causal prior anchors')
        else:
            _same(year_manifest.get('prior_thetas_before'), priors, 'year starting ridge anchors')
        _rng_state(diagnostics.get('rng_state'), 'year RNG checkpoint')
        previous_rng = diagnostics['rng_state']
        for key in ('increments', 'calibration_count', 'matrix_refresh_count'):
            if diagnostics.get(key) != per_year:
                _fail('year ' + key + ' count does not match every actual increment')
        if year_manifest.get('covariance_records') != per_year or entry.get('covariance_records') != per_year:
            _fail('year covariance count is incorrect')
        trajectory = _npz(_path(year_dir, 'trajectory.npz'),
                          ('states', 'maturities', 'state_names', 'elapsed_years', 'boundary_projections'))
        states = _array(trajectory['states'], (steps + 1, 3, d), 'reported states', True)
        elapsed = _array(trajectory['elapsed_years'], (steps + 1,), 'reported clock')
        _same(elapsed, year + np.arange(steps + 1) * dt, 'reported clock')
        _same(trajectory['maturities'], maturities, 'trajectory maturities')
        _labels(trajectory['state_names'], FAMILIES, 'trajectory states')
        _same(states[0], h[-1], 'year starting state')
        _trajectory_csv(_path(year_dir, 'trajectory.csv'), states, elapsed, maturities)
        cov_dir = _path(year_dir, 'covariance', directory=True)
        cov_manifest = _json(_path(cov_dir, 'manifest.json'))
        _schema(cov_manifest, 1, 'covariance manifest')
        if cov_manifest.get('increments') != per_year or cov_manifest.get('brownian_increment_records') != per_year:
            _fail('covariance archive has missing increments or shocks')
        _labels(cov_manifest.get('family_names'), FAMILIES, 'covariance families')
        _same(cov_manifest.get('maturities'), maturities, 'covariance maturities')
        _same(cov_manifest.get('elapsed_start_years'), 0., 'covariance year start')
        _same(cov_manifest.get('elapsed_end_years'), 1., 'covariance year end')
        inventory = cov_manifest.get('inventory')
        if not isinstance(inventory, dict) or inventory.get('records') != per_year:
            _fail('covariance inventory count mismatch')
        index_path = _path(cov_dir, inventory.get('file'))
        _hash(index_path, inventory.get('sha256'))
        checked_hashes += 1
        projections = np.zeros((3, d), dtype=np.int64)
        with index_path.open() as index:
            for increment in range(per_year):
                line = index.readline(128 * 1024 + 1)
                if not line or len(line) > 128 * 1024:
                    _fail('missing or oversized covariance inventory record')
                item = _loads(line)
                if not isinstance(item, dict) or item.get('step') != increment:
                    _fail('covariance steps are not consecutive')
                step_path = _path(cov_dir, item.get('file'))
                if item['file'] != 'step_%06d.npz' % increment:
                    _fail('covariance record filename does not match its step')
                _hash(step_path, item.get('sha256'))
                checked_hashes += 1
                record = _npz(step_path, (*MATRICES, 'regularization', 'state_before', 'state_after',
                                         'brownian_increments', 'coefficients', 'calibration_audit',
                                         'normal_shocks', 'step', 'elapsed_years', 'elapsed_end_years',
                                         'dt_years', 'maturities', 'family_names', 'coefficient_names'))
                _same(record['step'], increment, 'record step')
                for key, expected in (('elapsed_years', increment * delta),
                                      ('elapsed_end_years', (increment + 1) * delta), ('dt_years', delta)):
                    _same(item.get(key), expected, 'inventory ' + key)
                    _same(record[key], expected, 'record ' + key)
                _same(record['maturities'], maturities, 'record maturities')
                _labels(record['family_names'], FAMILIES, 'record families')
                _labels(record['coefficient_names'], ('theta', 'long_run_mean', 'diffusion'), 'record coefficients')
                _same(record['regularization'], alpha, 'record regularization')
                before = _array(record['state_before'], (3, d), 'state_before', True)
                after = _array(record['state_after'], (3, d), 'state_after', True)
                _same(before, h[-1], 'rolling state_before')
                matrices = {name: _array(record[name], (3, d, d), name) for name in MATRICES}
                for family in range(3):
                    expected_cov = np.atleast_2d(np.cov(h[:, family], rowvar=False, ddof=1))
                    _same(matrices['factor_covariance'][family], expected_cov, 'rolling level covariance')
                    deviations = np.sqrt(np.diag(expected_cov))
                    if (deviations <= 0).any():
                        _fail('zero-variance rolling history cannot define correlation')
                    raw = expected_cov / np.outer(deviations, deviations)
                    corr = (1-alpha) * raw + alpha * np.eye(d)
                    _same(matrices['raw_correlation'][family], raw, 'raw correlation')
                    _same(matrices['correlation'][family], corr, 'regularized correlation')
                    factor = matrices['cholesky'][family]
                    if (np.diag(factor) <= 0).any() or np.any(np.triu(factor, 1) != 0.):
                        _fail('Cholesky factor must be lower triangular with positive diagonal')
                    _same(factor @ factor.T, corr, 'Cholesky identity')
                    _same(matrices['brownian_covariance'][family], delta * corr, 'Brownian covariance')
                normals = _array(record['normal_shocks'], (3, d), 'normal shocks')
                dw = _array(record['brownian_increments'], (3, d), 'Brownian increments')
                expected_dw = np.stack([matrices['cholesky'][k].dot(normals[k]) * np.sqrt(delta) for k in range(3)])
                _same(dw, expected_dw, 'archived shock transformation')
                c = _array(record['coefficients'], (3, 3, d), 'coefficients', True)
                if (c[:, 0] <= 0).any() or (c[:, 0] * delta > 1.).any():
                    _fail('invalid or unstable coefficient speeds')
                audit_text = record['calibration_audit']
                if audit_text.shape != () or audit_text.dtype.kind not in 'US':
                    _fail('calibration audit must be one JSON string')
                audit = _loads(audit_text.item())
                if not isinstance(audit, dict) or audit.get('family_order') != list(FAMILIES):
                    _fail('calibration audit family order is invalid')
                if recalibrate:
                    fitted, expected_audits = _calibrate(h, maturities, clock, budget, fallback, priors)
                    _same(c[:, :2], fitted[:, :2], 'recalibrated drift coefficients')
                    _same(c[2, 2], fitted[2, 2], 'recalibrated terminal diffusion')
                    _audit_equal(audit, {'family_order': list(FAMILIES), 'families': expected_audits},
                                 'year %d increment %d calibration' % (year + 1, increment))
                replay = before.copy()
                for family in (2, 1, 0):
                    amplitude = c[2, 2] if family == 2 else replay[family + 1]
                    raw = (before[family] + c[family, 0] * (c[family, 1] - before[family]) * delta
                           + amplitude * np.sqrt(before[family]) * dw[family])
                    if not np.isfinite(raw).all():
                        _fail('nonfinite replayed increment')
                    projections[family] += raw < 0.
                    replay[family] = np.maximum(raw, 0.)
                _same(after, replay, 'ordered xi/sigma/rate update')
                _same(c[0, 2], after[1], 'actual rate diffusion')
                _same(c[1, 2], after[2], 'actual sigma diffusion')
                h[:-1], h[-1] = h[1:].copy(), after
                clock[:-1], clock[-1] = clock[1:].copy(), delta
                priors = c[:, 0].copy()
                if (increment + 1) % substeps == 0:
                    _same(states[(increment + 1) // substeps], after, 'reported endpoint')
            if index.read(1):
                _fail('covariance inventory contains extra records')
        _same(trajectory['boundary_projections'], projections, 'boundary projection counts')
        if entry.get('boundary_projections') != int(projections.sum()):
            _fail('year projection count mismatch')
        checkpoint = _npz(_path(year_dir, 'restart.npz'), ('history', 'history_dt', 'prior_thetas', 'maturities'))
        _same(checkpoint['history'], h, 'restart history')
        _same(checkpoint['history_dt'], clock, 'restart clock')
        _same(checkpoint['prior_thetas'], priors, 'restart ridge anchors')
        _same(checkpoint['maturities'], maturities, 'restart maturities')
        _same(diagnostics.get('prior_thetas'), priors, 'diagnostic ridge anchors')
        _same(diagnostics.get('final_history_elapsed_years'), clock.sum(), 'final history clock span')
        total_increments += per_year
        total_projections += int(projections.sum())
        # Do not retain the preceding annual trajectory while opening the next.
        del trajectory, states, elapsed, checkpoint
    return {'status': 'verified', 'years': years, 'increments': total_increments,
            'checked_sha256': checked_hashes, 'recalibrated_increments': total_increments if recalibrate else 0,
            'boundary_projections': total_projections, 'new_random_draws': 0,
            'rng_checkpoint_continuity': 'verified; archived draws are not regenerated'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify hashes and replay every archived walk increment without new draws.')
    parser.add_argument('--input', required=True, help='completed walk directory inside the repository')
    parser.add_argument('--recalibrate', action='store_true', help='also refit every causal history and compare coefficients and audits')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify_walk(args.input, args.recalibrate), indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
        parser.exit(2, 'Walk verification failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
