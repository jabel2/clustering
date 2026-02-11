import pandas as pd
import numpy as np
import random
from datetime import datetime
import argparse


def generate_ad_data(
    n: int = 1000,
    outlier_pct: float = 1.5,
    n_outliers: int | None = None,
    seed: int = 42,
):
    """Generate synthetic AD group data with controllable outliers.

    Args:
        n: Total number of records to generate.
        outlier_pct: Percentage of records that should be outliers (ignored if n_outliers set).
        n_outliers: Exact number of outliers to generate (overrides outlier_pct).
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with generated data.
    """
    np.random.seed(seed)
    random.seed(seed)

    # Calculate outlier count
    if n_outliers is not None:
        num_outliers = n_outliers
    else:
        num_outliers = max(1, int(n * outlier_pct / 100))

    num_normal = n - num_outliers

    # Define standard clusters
    depts = ['IT', 'HR', 'Sales', 'Finance', 'Marketing']
    locations = ['New York', 'London', 'Tokyo', 'Austin']
    titles = {
        'IT': ['DevOps Engineer', 'System Admin', 'Data Scientist'],
        'Sales': ['Account Manager', 'Sales Rep', 'VP of Sales'],
        'HR': ['Recruiter', 'HR Business Partner'],
        'Finance': ['Analyst', 'Controller'],
        'Marketing': ['SEO Specialist', 'Content Creator']
    }

    data = []

    # Generate "Normal" users
    for i in range(num_normal):
        dept = random.choice(depts)
        data.append({
            'user_id': f'U{1000+i}',
            'display_name': f'User_{i}',
            'department': dept,
            'job_title': random.choice(titles[dept]),
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': max(1, int(np.random.normal(1200, 400))),
            'is_contractor': random.choice([0, 0, 0, 1]),  # 25% chance
            'manager_level': random.randint(1, 4)
        })

    # Generate outliers with different types
    outliers = []

    # Distribute outliers across different anomaly types
    # Type 1: "Subtle" outliers (harder to detect) - ~20% of outliers
    # Type 2: "Moderate" outliers - ~30% of outliers
    # Type 3: "Obvious" outliers - ~50% of outliers

    n_subtle = max(1, int(num_outliers * 0.2))
    n_moderate = max(1, int(num_outliers * 0.3))
    n_obvious = num_outliers - n_subtle - n_moderate

    outlier_id = 1

    # Diverse anomaly patterns for variety
    anomalous_titles = [
        'Chief Happiness Officer', 'Ninja Developer', 'Growth Hacker',
        'Dream Facilitator', 'Chaos Coordinator', 'Innovation Catalyst',
        'Digital Prophet', 'Synergy Specialist', 'Unicorn Wrangler',
        'Chief Everything Officer', 'Reality Checker', 'Pixel Perfectionist'
    ]
    anomalous_locations = [
        'Remote_Moon', 'Antarctica Base', 'Underwater Lab', 'Space Station',
        'Classified', 'Offshore Platform', 'Mountain Bunker', 'Desert Outpost'
    ]

    # Type 1: Subtle outliers (hard to detect - only 1 attribute is slightly off)
    # Each one is different, blends in with normal data
    subtle_patterns = [
        # Pattern: Wrong title for department (but title exists in another dept)
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': random.choice(titles[random.choice([d for d in depts if d != dept])]),
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': int(np.random.normal(1200, 400)),
            'is_contractor': 0,
            'manager_level': random.randint(1, 4)
        },
        # Pattern: Slightly high tenure for role
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': random.choice(titles[dept]),
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': random.randint(2500, 3500),  # High but not extreme
            'is_contractor': 0,
            'manager_level': random.randint(1, 2)  # Low level despite tenure
        },
        # Pattern: Contractor with slightly elevated access
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': random.choice(titles[dept]),
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': random.randint(100, 400),
            'is_contractor': 1,
            'manager_level': 4  # Slightly high for contractor
        },
    ]

    for i in range(n_subtle):
        pattern = random.choice(subtle_patterns)
        record = pattern()
        record['user_id'] = f'OUT_{outlier_id}'
        record['display_name'] = f'User_{random.randint(100, 999)}'
        outliers.append(record)
        outlier_id += 1

    # Type 2: Moderate outliers (2-3 attributes are unusual)
    # Each has a different combination of anomalies
    moderate_patterns = [
        # Pattern: New hire with high access
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': 'Intern',
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': random.randint(1, 30),
            'is_contractor': random.choice([0, 1]),
            'manager_level': random.randint(6, 8)
        },
        # Pattern: Mismatched business unit
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': random.choice(titles[dept]),
            'location': random.choice(locations),
            'business_unit': f'{random.choice([d for d in depts if d != dept])}_Unit',
            'tenure_days': random.randint(500, 1500),
            'is_contractor': 0,
            'manager_level': random.randint(3, 5)
        },
        # Pattern: Long-term contractor with management role
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': 'Consultant',
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': random.randint(4000, 6000),
            'is_contractor': 1,
            'manager_level': random.randint(5, 7)
        },
        # Pattern: Entry role with very long tenure
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': 'Temp Worker',
            'location': random.choice(locations),
            'business_unit': f'{dept}_Unit',
            'tenure_days': random.randint(3000, 5000),
            'is_contractor': 1,
            'manager_level': random.randint(1, 2)
        },
        # Pattern: Executive level in wrong location
        lambda: {
            'department': (dept := random.choice(depts)),
            'job_title': random.choice(titles[dept]),
            'location': random.choice(anomalous_locations[:4]),  # Unusual but not extreme
            'business_unit': f'{dept}_Unit',
            'tenure_days': random.randint(800, 1500),
            'is_contractor': 0,
            'manager_level': random.randint(1, 2)
        },
    ]

    for i in range(n_moderate):
        pattern = random.choice(moderate_patterns)
        record = pattern()
        record['user_id'] = f'OUT_{outlier_id}'
        record['display_name'] = f'User_{random.randint(100, 999)}'
        outliers.append(record)
        outlier_id += 1

    # Type 3: Obvious outliers (clearly anomalous but DIVERSE - each is unique)
    # Mix different extreme attributes so they don't cluster together
    for i in range(n_obvious):
        dept = random.choice(depts)

        # Randomly select which attributes to make anomalous
        use_anomalous_title = random.choice([True, False])
        use_anomalous_location = random.choice([True, False])
        use_extreme_tenure = random.choice([True, False])
        use_extreme_level = random.choice([True, False])
        use_wrong_unit = random.choice([True, False])

        # Ensure at least 2 anomalies
        anomaly_count = sum([use_anomalous_title, use_anomalous_location,
                           use_extreme_tenure, use_extreme_level, use_wrong_unit])
        if anomaly_count < 2:
            use_anomalous_title = True
            use_extreme_tenure = True

        outliers.append({
            'user_id': f'OUT_{outlier_id}',
            'display_name': f'User_{random.randint(100, 999)}',
            'department': dept,
            'job_title': random.choice(anomalous_titles) if use_anomalous_title else random.choice(titles[dept]),
            'location': random.choice(anomalous_locations) if use_anomalous_location else random.choice(locations),
            'business_unit': f'{random.choice([d for d in depts if d != dept])}_Unit' if use_wrong_unit else f'{dept}_Unit',
            'tenure_days': random.randint(8000, 20000) if use_extreme_tenure else random.randint(-100, 0),  # Extreme high or negative
            'is_contractor': random.choice([0, 1]),
            'manager_level': random.randint(8, 10) if use_extreme_level else random.randint(1, 4)
        })
        outlier_id += 1

    df = pd.DataFrame(data + outliers)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic AD group test data')
    parser.add_argument('-n', '--records', type=int, default=1000,
                        help='Total number of records to generate (default: 1000)')
    parser.add_argument('-p', '--outlier-pct', type=float, default=1.5,
                        help='Percentage of outliers (default: 1.5)')
    parser.add_argument('-o', '--n-outliers', type=int, default=None,
                        help='Exact number of outliers (overrides --outlier-pct)')
    parser.add_argument('-s', '--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file path (default: auto-generated with timestamp)')

    args = parser.parse_args()

    df = generate_ad_data(
        n=args.records,
        outlier_pct=args.outlier_pct,
        n_outliers=args.n_outliers,
        seed=args.seed,
    )

    # Count actual outliers
    actual_outliers = len(df[df['user_id'].str.startswith('OUT_')])

    if args.output:
        output_path = args.output
    else:
        output_path = f'C:\\Users\\Abel\\Desktop\\mobile-app\\clustering\\data\\samples\\ad_test_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    df.to_csv(output_path, index=True)

    # Convert to relative path for CLI commands
    relative_path = output_path.replace('C:\\Users\\Abel\\Desktop\\mobile-app\\clustering\\', '').replace('\\', '/')

    print(f"Generated {len(df)} records:")
    print(f"  - Normal users: {len(df) - actual_outliers}")
    print(f"  - Outliers: {actual_outliers} ({actual_outliers/len(df)*100:.1f}%)")
    print(f"Saved to: {output_path}")
    print()
    print("=" * 60)
    print("Run these commands to analyze the data:")
    print("=" * 60)
    print()
    print("# DBCV method (optimizes cluster quality with outlier penalty):")
    print(f"python cli.py analyze {relative_path} --id-column user_id --auto-cluster-size")
    print()
    print("# Balanced method (targets 5-15% outlier rate):")
    print(f"python cli.py analyze {relative_path} --id-column user_id --auto-cluster-size --auto-method balanced")
    print()
    print("# Heuristic method (log2-based, often best for outlier detection):")
    print(f"python cli.py analyze {relative_path} --id-column user_id --auto-cluster-size --auto-method heuristic")
    print()
    print("# With LLM explanation:")
    print(f"python cli.py explain {relative_path} --id-column user_id --auto-cluster-size --auto-method heuristic --context \"AD group test data\"")
    print()


if __name__ == '__main__':
    main()