"""Download the execution summary and pod-hourly day 0 through day 29."""

from download_and_extract_pod_days import main as download_pod_days
from download_job_summary import main as download_job_summary


def main() -> None:
    download_job_summary()
    download_pod_days()


if __name__ == "__main__":
    main()

