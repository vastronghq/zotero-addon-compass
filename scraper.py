import datetime
import os
import sys
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 文件名配置
CSV_FILENAME = "zotero_addons_info.csv"
README_FILENAME = "README.md"

# GitHub API 请求头（建议在环境变量中设置 GITHUB_TOKEN 以获得每小时 5000 次的请求限额）
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/vnd.github.v3+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


def create_session():
    """创建带有网络自动重试机制的 Session，提高稳定性"""
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
    """获取 syt2/zotero-addons-scraper/addons 路径下的所有目录/文件名"""
    api_url = "https://api.github.com/repos/syt2/zotero-addons-scraper/contents/addons"
    try:
        response = SESSION.get(api_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"获取 addons 目录失败，HTTP 状态码: {response.status_code}")
            return []
        items = response.json()
        return [item["name"] for item in items]
    except Exception as e:
        print(f"获取 addons 列表发生网络错误: {e}")
        return []


def parse_repo_info(folder_name):
    """抓取仓库的 Star、Issue、最后更新、最新 Release 版本及下载量等信息"""
    if "@" not in folder_name:
        print(f"跳过不符合格式的项: {folder_name}")
        return None

    owner, repo_name = folder_name.split("@", 1)
    target_url = f"https://github.com/{owner}/{repo_name}"
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    print(f"正在抓取: {target_url}")

    try:
        res = SESSION.get(api_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()

            # ISO 8601 时间格式化转换为本地/简洁日期
            pushed_at = data.get("pushed_at", "")
            last_updated = pushed_at.split("T")[0] if pushed_at else "N/A"

            # 获取 Release 信息及总下载量
            releases_url = f"{api_url}/releases"
            rel_res = SESSION.get(releases_url, headers=HEADERS, timeout=10)

            latest_release = "No Release"
            total_downloads = 0

            if rel_res.status_code == 200:
                releases = rel_res.json()
                if releases and isinstance(releases, list):
                    # 获取最新非 draft/prerelease 版本（没有则取第一个）
                    valid_releases = [
                        r
                        for r in releases
                        if not r.get("draft") and not r.get("prerelease")
                    ]
                    latest = valid_releases[0] if valid_releases else releases[0]
                    latest_release = latest.get("tag_name", "N/A")

                    # 统计所有 release 的 asset 总下载量
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
            print(f"仓库不存在或已被删除: {target_url}")
            return {
                "Folder Name": folder_name,
                "Addon Name": folder_name,
                "About": "[仓库已移除或删库 (404)]",
                "Stars": 0,
                "Last Updated": "N/A",
                "Latest Release": "N/A",
                "Open Issues": 0,
                "Download Count": 0,
                "Repository URL": target_url,
                "Is_Exist": False,
            }
        else:
            print(f"请求失败 ({res.status_code}): {target_url}")
            return None

    except Exception as e:
        print(f"抓取 {target_url} 异常: {e}")
        return None


def load_existing_history(csv_path):
    """读取已有 CSV，恢复 Features、Evaluation 以及记录旧 Star 数计算 Star Diff"""
    history_data = {}
    if os.path.exists(csv_path):
        try:
            df_old = pd.read_csv(csv_path, dtype=str)
            for _, row in df_old.iterrows():
                key = row.get("Folder Name") or row.get("Addon Name")
                if key:
                    stars_val = row.get("Stars", 0)
                    try:
                        stars_int = int(stars_val)
                    except ValueError:
                        stars_int = 0

                    history_data[key] = {
                        "Features": row.get("Features", "")
                        if pd.notna(row.get("Features"))
                        else "",
                        "Evaluation": row.get("Evaluation", "")
                        if pd.notna(row.get("Evaluation"))
                        else "",
                        "Old_Stars": stars_int,
                        "Full_Row": row.to_dict(),  # 保存旧数据用于保留已完全失效删库的历史记录
                    }
            print(
                f"发现已有 CSV 文件，已载入 {len(history_data)} 条历史标注与星数数据。"
            )
        except Exception as e:
            print(f"读取历史 CSV 文件失败: {e}")
    else:
        print("未发现历史 CSV 文件，将直接创建新文件。")

    return history_data


def generate_readme(df, readme_path):
    """根据最新的 DataFrame 数据生成排版优美、带有超链接的 README.md 文档"""
    updated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    markdown_lines = [
        "# Zotero Addon Monitor & Personal Reviews",
        "This repository is dedicated to tracking and recording my personal experiences with different Zotero addons. It aims to discover interesting, practical addons while minimize the time cost of redundant trial and error. (Note: Based on personal, subjective experience and non-exhaustive use.)",
        f"\n> **Auto-updated at:**：`{updated_time}` | Total addons: **{len(df)}**\n",
        "| Addon Name | Stars | Star Diff | Last Updated | Release | Download | Features | Evaluation | About |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- | :--- |",
    ]

    for _, row in df.iterrows():
        name = str(row["Addon Name"]).replace("|", "\\|")
        url = row["Repository URL"]
        stars = row["Stars"]
        diff = row["Star Diff"]
        updated = row["Last Updated"]
        release = row["Latest Release"]
        downloads = row["Download Count"]
        features = (
            str(row["Features"]).replace("\n", " ") if pd.notna(row["Features"]) else ""
        )
        eval_text = (
            str(row["Evaluation"]).replace("\n", " ")
            if pd.notna(row["Evaluation"])
            else ""
        )
        about = str(row["About"]).replace("\n", " ") if pd.notna(row["About"]) else ""

        # 格式化 Star Diff 显示
        if str(diff).startswith("+"):
            diff_str = f"🟢 `{diff}`"
        elif str(diff).startswith("-"):
            diff_str = f"🔴 `{diff}`"
        else:
            diff_str = "`0`"

        name_link = f"[{name}]({url})" if url.startswith("http") else name

        line = f"| {name_link} | ⭐ {stars} | {diff_str} | {updated} | {release} | {int(downloads):,} | {features} | {eval_text} | {about} |"
        markdown_lines.append(line)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_lines))

    print(f"已成功渲染并输出 Markdown 文档到 `{readme_path}`")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "render":
        print("正在更新 README.md ...")
        if os.path.exists(CSV_FILENAME):
            df = pd.read_csv(CSV_FILENAME, dtype=str)
            generate_readme(df, README_FILENAME)
        else:
            print(f"错误：未找到 {CSV_FILENAME}")
        return

    # 1. 加载旧数据
    history_data = load_existing_history(CSV_FILENAME)

    # 2. 获取 addons 目录下的文件夹列表
    print("\n开始获取最新 addons 列表...")
    folders = get_addon_folders()
    print(f"共获取到 {len(folders)} 个文件/文件夹名称。\n")

    scraped_results = []
    scraped_keys = set()

    # 3. 逐个抓取仓库信息
    for folder in folders:
        info = parse_repo_info(folder)
        if info:
            key = folder
            scraped_keys.add(key)

            history = history_data.get(key, {})

            # 恢复 Features 和 Evaluation
            info["Features"] = history.get("Features", "")
            info["Evaluation"] = history.get("Evaluation", "")

            # 计算 Star Diff (增量)
            old_stars = history.get("Old_Stars", None)
            new_stars = info["Stars"]

            if old_stars is not None:
                diff = new_stars - old_stars
                info["Star Diff"] = f"+{diff}" if diff > 0 else str(diff)
            else:
                info["Star Diff"] = "New"

            scraped_results.append(info)

        # 每次抓取后暂停 0.4 秒，防止 API 触发限流
        time.sleep(0.4)

    # 4. 保留那些原先存在，但本次在 GitHub 列表中被彻底删掉的项目记录
    for old_key, old_val in history_data.items():
        if old_key not in scraped_keys:
            old_row = old_val.get("Full_Row", {})
            old_row["About"] = "[已被从列表中移除]"
            old_row["Star Diff"] = "0"
            scraped_results.append(old_row)

    if not scraped_results:
        print("未获取到任何有效数据，程序中断。")
        return

    # 5. 构建 DataFrame、格式化并按 Stars 降序排列
    df = pd.DataFrame(scraped_results)

    df["Stars"] = pd.to_numeric(df["Stars"], errors="coerce").fillna(0).astype(int)
    df["Download Count"] = (
        pd.to_numeric(df["Download Count"], errors="coerce").fillna(0).astype(int)
    )
    df["Open Issues"] = (
        pd.to_numeric(df["Open Issues"], errors="coerce").fillna(0).astype(int)
    )

    column_order = [
        "Addon Name",
        "Folder Name",
        "Stars",
        "Star Diff",
        "Last Updated",
        "Latest Release",
        "Open Issues",
        "Download Count",
        "Features",
        "Evaluation",
        "About",
        "Repository URL",
    ]

    # 确保所有列均在 DataFrame 中
    for col in column_order:
        if col not in df.columns:
            df[col] = ""

    df = df[column_order]
    df = df.sort_values(by="Stars", ascending=False)

    # 6. 保存 CSV 与 Markdown 文档
    df.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\n全量数据已保存至 CSV: {CSV_FILENAME}")

    generate_readme(df, README_FILENAME)


if __name__ == "__main__":
    main()
