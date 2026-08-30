import datetime
import os
import sys
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Filename configuration
CSV_FILENAME = "zotero_addons_info.csv"
README_FILENAME = "README.md"

# GitHub API headers (set GITHUB_TOKEN in environment variables for a limit of 5000 requests/hour)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/vnd.github.v3+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


def create_session():
    """Create a Session with automatic retry mechanism to improve stability."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = create_session()


def get_addon_folders():
    """Get all directory/file names under syt2/zotero-addons-scraper/addons path."""
    api_url = "https://api.github.com/repos/syt2/zotero-addons-scraper/contents/addons"
    try:
        response = SESSION.get(api_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(
                f"Failed to get addons directory, HTTP status code: {response.status_code}"
            )
            return []
        items = response.json()
        return [item["name"] for item in items]
    except Exception as e:
        print(f"Network error while fetching addons list: {e}")
        return []


def parse_repo_info(folder_name):
    """Scrape repository info such as Stars, Issues, Last Updated, Latest Release version, and Download Count."""
    if "@" not in folder_name:
        print(f"Skipping improperly formatted item: {folder_name}")
        return None

    owner, repo_name = folder_name.split("@", 1)
    target_url = f"https://github.com/{owner}/{repo_name}"
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    print(f"Scraping: {target_url}")

    scrape_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        res = SESSION.get(api_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()

            # Format ISO 8601 timestamp to local/concise date format
            pushed_at = data.get("pushed_at", "")
            last_updated = pushed_at.split("T")[0] if pushed_at else "N/A"

            # Get Release information and total download count
            releases_url = f"{api_url}/releases"
            rel_res = SESSION.get(releases_url, headers=HEADERS, timeout=10)

            latest_release = "No Release"
            total_downloads = 0

            if rel_res.status_code == 200:
                releases = rel_res.json()
                if releases and isinstance(releases, list):
                    # Get the latest non-draft/non-prerelease version (if none, take the first one)
                    valid_releases = [
                        r
                        for r in releases
                        if not r.get("draft") and not r.get("prerelease")
                    ]
                    latest = valid_releases[0] if valid_releases else releases[0]
                    latest_release = latest.get("tag_name", "N/A")

                    # Calculate total asset download count across all releases
                    for rel in releases:
                        for asset in rel.get("assets", []):
                            total_downloads += asset.get("download_count", 0)

            return {
                "Scrape Time": scrape_time,
                "Folder Name": folder_name,
                "Addon Name": data.get("name", repo_name),
                "About": data.get("description", "") or "",
                "Stars": data.get("stargazers_count", 0),
                "Last Updated": last_updated,
                "Latest Release": latest_release,
                "Open Issues": data.get("open_issues_count", 0),
                "Download Count": total_downloads,
                "Repository URL": target_url,
                "Is_Exist": True,
            }

        elif res.status_code == 404:
            print(f"Repository does not exist or has been deleted: {target_url}")
            return {
                "Scrape Time": scrape_time,
                "Folder Name": folder_name,
                "Addon Name": folder_name,
                "About": "[Repository removed or deleted (404)]",
                "Stars": 0,
                "Last Updated": "N/A",
                "Latest Release": "N/A",
                "Open Issues": 0,
                "Download Count": 0,
                "Repository URL": target_url,
                "Is_Exist": False,
            }
        else:
            print(f"Request failed ({res.status_code}): {target_url}")
            return None

    except Exception as e:
        print(f"Exception while scraping {target_url}: {e}")
        return None
    """Scrape repository info such as Stars, Issues, Last Updated, Latest Release version, and Download Count."""
    if "@" not in folder_name:
        print(f"Skipping improperly formatted item: {folder_name}")
        return None

    owner, repo_name = folder_name.split("@", 1)
    target_url = f"https://github.com/{owner}/{repo_name}"
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    print(f"Scraping: {target_url}")

    try:
        res = SESSION.get(api_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()

            # Format ISO 8601 timestamp to local/concise date format
            pushed_at = data.get("pushed_at", "")
            last_updated = pushed_at.split("T")[0] if pushed_at else "N/A"

            # Get Release information and total download count
            releases_url = f"{api_url}/releases"
            rel_res = SESSION.get(releases_url, headers=HEADERS, timeout=10)

            latest_release = "No Release"
            total_downloads = 0

            if rel_res.status_code == 200:
                releases = rel_res.json()
                if releases and isinstance(releases, list):
                    # Get the latest non-draft/non-prerelease version (if none, take the first one)
                    valid_releases = [
                        r
                        for r in releases
                        if not r.get("draft") and not r.get("prerelease")
                    ]
                    latest = valid_releases[0] if valid_releases else releases[0]
                    latest_release = latest.get("tag_name", "N/A")

                    # Calculate total asset download count across all releases
                    for rel in releases:
                        for asset in rel.get("assets", []):
                            total_downloads += asset.get("download_count", 0)

            return {
                "Folder Name": folder_name,
                "Addon Name": data.get("name", repo_name),
                "About": data.get("description", "") or "",
                "Stars": data.get("stargazers_count", 0),
                "Last Updated": last_updated,
                "Latest Release": latest_release,
                "Open Issues": data.get("open_issues_count", 0),
                "Download Count": total_downloads,
                "Repository URL": target_url,
                "Is_Exist": True,
            }

        elif res.status_code == 404:
            print(f"Repository does not exist or has been deleted: {target_url}")
            return {
                "Folder Name": folder_name,
                "Addon Name": folder_name,
                "About": "[Repository removed or deleted (404)]",
                "Stars": 0,
                "Last Updated": "N/A",
                "Latest Release": "N/A",
                "Open Issues": 0,
                "Download Count": 0,
                "Repository URL": target_url,
                "Is_Exist": False,
            }
        else:
            print(f"Request failed ({res.status_code}): {target_url}")
            return None

    except Exception as e:
        print(f"Exception while scraping {target_url}: {e}")
        return None


def load_existing_history(csv_path):
    """Read existing CSV to restore Features and Reviews content and keep historical items."""
    history_data = {}
    if os.path.exists(csv_path):
        try:
            df_old = pd.read_csv(csv_path, dtype=str)
            for _, row in df_old.iterrows():
                key = row.get("Folder Name") or row.get("Addon Name")
                if key:
                    history_data[key] = {
                        "Features": row.get("Features", "")
                        if pd.notna(row.get("Features"))
                        else "",
                        "Reviews": row.get("Reviews", "")
                        if pd.notna(row.get("Reviews"))
                        else "",
                        "Full_Row": row.to_dict(),  # Save old data to retain historical records of deleted repositories
                    }
            print(
                f"Found existing CSV file, loaded {len(history_data)} historical annotated entries."
            )
        except Exception as e:
            print(f"Failed to read existing CSV file: {e}")
    else:
        print("No existing CSV file found, creating a new one directly.")

    return history_data


def generate_readme(df, readme_path):
    """Generate a well-formatted README.md document with hyperlinks based on the latest DataFrame data."""
    updated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    markdown_lines = [
        "# Zotero Addon Monitor & Personal Reviews",
        "This repository is dedicated to tracking and recording my personal experiences with different Zotero addons. It aims to discover interesting, practical addons while minimize the time cost of redundant trial and error. (Note: Based on personal, subjective experience and non-exhaustive use.)",
        f"\n> **Auto-updated at:** `{updated_time}` | Total addons: **{len(df)}**\n",
        "| Addon Name | Stars | New | Features | Reviews | Last Updated | Release | Download | About |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- | :--- |",
    ]

    for _, row in df.iterrows():
        name = str(row["Addon Name"]).replace("|", "\\|")
        url = row["Repository URL"]
        stars = row["Stars"]
        is_new = row["New"]
        updated = row["Last Updated"]
        release = row["Latest Release"]
        downloads = row["Download Count"]
        features = (
            str(row["Features"]).replace("\n", " ") if pd.notna(row["Features"]) else ""
        )
        review_text = (
            str(row["Reviews"]).replace("\n", " ") if pd.notna(row["Reviews"]) else ""
        )
        about = str(row["About"]).replace("\n", " ") if pd.notna(row["About"]) else ""

        # Format New tag display
        new_str = "🟢 `New`" if is_new == "New" else ""

        name_link = f"[{name}]({url})" if url.startswith("http") else name

        line = f"| {name_link} | ⭐ {stars} | {new_str} | {features} | {review_text} | {updated} | {release} | {int(downloads):,} | {about} |"
        markdown_lines.append(line)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_lines))

    print(f"Successfully rendered and output Markdown document to `{readme_path}`")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "render":
        print("Updating README.md ...")
        if os.path.exists(CSV_FILENAME):
            df = pd.read_csv(CSV_FILENAME, dtype=str)
            generate_readme(df, README_FILENAME)
        else:
            print(f"Error: {CSV_FILENAME} not found")
        return

    # 1. Load historical data
    history_data = load_existing_history(CSV_FILENAME)

    # 2. Get folder list under addons directory
    print("\nStarting to fetch latest addons list...")
    folders = get_addon_folders()
    print(f"Fetched {len(folders)} file/folder names in total.\n")

    scraped_results = []
    scraped_keys = set()

    # 3. Scrape repository info one by one
    for folder in folders:
        info = parse_repo_info(folder)
        if info:
            key = folder
            scraped_keys.add(key)

            history = history_data.get(key, None)

            if history is not None:
                # History exists: restore Features and Reviews, clear New tag
                info["Features"] = history.get("Features", "")
                info["Reviews"] = history.get("Reviews", "")
                info["New"] = ""
            else:
                # History does not exist: mark as new addon added in this run
                info["Features"] = ""
                info["Reviews"] = ""
                info["New"] = "New"

            scraped_results.append(info)

        # Pause 0.4 seconds after each scrape to prevent hitting API rate limits
        time.sleep(0.4)

    # 4. Retain records that previously existed but were removed from the GitHub list in this run
    for old_key, old_val in history_data.items():
        if old_key not in scraped_keys:
            old_row = old_val.get("Full_Row", {})
            old_row["About"] = "[Removed from the list]"
            old_row["New"] = ""
            scraped_results.append(old_row)

    if not scraped_results:
        print("No valid data fetched, program aborted.")
        return

    # 5. Build DataFrame, format, and sort by Stars descending
    df = pd.DataFrame(scraped_results)

    df["Stars"] = pd.to_numeric(df["Stars"], errors="coerce").fillna(0).astype(int)
    df["Download Count"] = (
        pd.to_numeric(df["Download Count"], errors="coerce").fillna(0).astype(int)
    )
    df["Open Issues"] = (
        pd.to_numeric(df["Open Issues"], errors="coerce").fillna(0).astype(int)
    )

    # 将 "Scrape Time" 放在第一列
    column_order = [
        "Scrape Time",
        "Addon Name",
        "Folder Name",
        "Stars",
        "New",
        "Features",
        "Reviews",
        "Last Updated",
        "Latest Release",
        "Open Issues",
        "Download Count",
        "About",
        "Repository URL",
    ]

    # Ensure all columns exist in DataFrame
    for col in column_order:
        if col not in df.columns:
            df[col] = ""

    df = df[column_order]
    df = df.sort_values(by=["New", "Stars"], ascending=[False, False])

    # 6. Save CSV and Markdown document
    df.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\nFull dataset saved to CSV: {CSV_FILENAME}")

    generate_readme(df, README_FILENAME)


if __name__ == "__main__":
    main()
