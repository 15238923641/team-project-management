#!/usr/bin/env python3
# =============================================================================
# GitHub Label Color Standardization Verification Script
# 标签颜色标准化验证脚本：验证GitHub项目的标签标准化流程
# 依赖：requests, python-dotenv（安装：pip install requests python-dotenv）
# =============================================================================

import sys
import os
import requests
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv


# --------------------------
# 1. 通用工具函数
# --------------------------
def _get_github_api(
    endpoint: str, headers: Dict[str, str], org: str, repo: str
) -> Tuple[bool, Optional[Dict]]:
    """通用GitHub API请求函数：发起GET请求，返回（请求成功状态，响应数据）"""
    url = f"https://api.github.com/repos/{org}/{repo}/{endpoint}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return True, response.json()
        elif response.status_code == 404:
            print(f"[API提示] {endpoint} 资源未找到（404）", file=sys.stderr)
            return False, None
        else:
            print(f"[API错误] {endpoint} 状态码：{response.status_code}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"[API异常] 调用 {endpoint} 失败：{str(e)}", file=sys.stderr)
        return False, None


def _check_branch_exists(
    branch_name: str, headers: Dict[str, str], org: str, repo: str
) -> bool:
    """验证目标分支是否存在"""
    success, _ = _get_github_api(f"branches/{branch_name}", headers, org, repo)
    return success


def _get_file_content(
    branch: str, file_path: str, headers: Dict[str, str], org: str, repo: str
) -> Optional[str]:
    """从指定分支获取文件内容（Base64解码）"""
    import base64

    success, result = _get_github_api(
        f"contents/{file_path}?ref={branch}", headers, org, repo
    )
    if not success or not result:
        return None

    if result.get("content"):
        try:
            return base64.b64decode(result["content"]).decode("utf-8")
        except Exception as e:
            print(f"[文件解码错误] {file_path}：{str(e)}", file=sys.stderr)
            return None
    return None


def _parse_label_table(content: str, table_header: str) -> List[str]:
    """通用标签表格解析：从Markdown内容中提取标签名（支持自定义表格头部）"""
    documented_labels = []
    lines = content.split("\n")
    in_table = False

    for line in lines:
        # 识别表格头部（支持配置化）
        if table_header in line:
            in_table = True
            continue
        # 跳过表格分隔线（如"|---|---|---|"）
        if in_table and line.startswith("|---"):
            continue
        # 解析表格行（按"| 内容 | 内容 | 内容 |"格式）
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:  # 匹配"空|标签名|颜色|分类|空"格式
                label_name = parts[1]
                if label_name and label_name != "Label Name":  # 跳过表头
                    documented_labels.append(label_name)
        # 识别表格结束（遇到非表格行）
        if in_table and line and not line.startswith("|"):
            break

    return documented_labels


def _find_issue_by_keywords(
    title_keywords: List[str], headers: Dict[str, str], org: str, repo: str
) -> Optional[Dict]:
    """按标题关键词查找Issue（支持匹配多个关键词，忽略大小写）"""
    for state in ["open", "closed"]:
        success, issues = _get_github_api(
            f"issues?state={state}&per_page=30", headers, org, repo
        )
        if success and issues:
            for issue in issues:
                # 跳过PR（仅匹配纯Issue）
                if "pull_request" in issue:
                    continue
                title = issue.get("title", "").lower()
                if all(kw.lower() in title for kw in title_keywords):
                    return issue
    return None


def _find_pr_by_keywords(
    title_keywords: List[str], headers: Dict[str, str], org: str, repo: str
) -> Optional[Dict]:
    """按标题关键词查找PR（支持匹配多个关键词，忽略大小写）"""
    for state in ["open", "closed"]:
        success, prs = _get_github_api(
            f"pulls?state={state}&per_page=30", headers, org, repo
        )
        if success and prs:
            for pr in prs:
                title = pr.get("title", "").lower()
                if all(kw.lower() in title for kw in title_keywords):
                    return pr
    return None


def _get_issue_comments(
    issue_number: int, headers: Dict[str, str], org: str, repo: str
) -> List[Dict]:
    """获取指定Issue的所有评论"""
    success, comments = _get_github_api(
        f"issues/{issue_number}/comments", headers, org, repo
    )
    return comments if (success and comments) else []


# --------------------------
# 2. 核心验证流程
# --------------------------
def verify_label_standardization() -> bool:
    """标签颜色标准化验证主流程：按配置完成全链路校验"""
    
    # 配置常量（根据实际项目调整）
    CONFIG = {
        # 目标仓库信息
        "target_repo": "team-project-management",
        # 功能分支配置
        "feature_branch": {
            "name": "feat/label-color-standard",
            "doc_file": "docs/label-color-standardization.md"
        },
        # 标签文档解析配置
        "doc_parsing": {
            "table_header": "| Label Name | Color Hex | Category |",
            "min_label_count": 22
        },
        # Issue验证配置
        "issue_requirements": {
            "title_keywords": ["Label", "standard", "documentation"],
            "body_keywords": ["label", "color", "standard"],
            "required_sections": ["## Background", "## Required Label List"],
            "initial_labels": ["documentation", "enhancement"]
        },
        # PR验证配置
        "pr_requirements": {
            "title_keywords": ["Label", "standard", "documentation"],
            "body_keywords": ["label", "documentation", "standard"],
            "required_sections": ["## Summary", "## Changes"],
            "min_labels_count": 3,
            "issue_reference_pattern": "Fixes #{issue_number}"
        },
        # 预期标签配置（示例标签列表）
        "expected_labels": [
            "bug", "enhancement", "documentation", "feature", "bug-critical", 
            "bug-major", "bug-minor", "task", "question", "help-wanted",
            "good-first-issue", "priority-high", "priority-medium", "priority-low",
            "status-in-progress", "status-review", "status-done", "status-blocked",
            "component-frontend", "component-backend", "component-db", "wontfix"
        ],
        # Issue评论验证配置
        "comment_requirements": {
            "keywords": ["label", "documentation", "completed"],
            "pr_reference_flag": "PR #{pr_number}",
            "content_flags": ["labels", "verified", "applied"]
        }
    }

    # --------------------------
    # 步骤1：加载环境变量
    # --------------------------
    load_dotenv(".env")
    github_token = os.environ.get("GITHUB_TOKEN")
    github_org = os.environ.get("GITHUB_ORG")

    # 校验环境变量
    if not github_token:
        print("[环境错误] 未配置 GITHUB_TOKEN（需在 .env 中设置）", file=sys.stderr)
        return False
    if not github_org:
        print("[环境错误] 未配置 GITHUB_ORG（需在 .env 中设置）", file=sys.stderr)
        return False

    # 构建API请求头
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    print("=" * 60)
    print("开始执行标签颜色标准化验证（GitHub场景）")
    print(f"目标仓库：{github_org}/{CONFIG['target_repo']}")
    print("=" * 60)

    # --------------------------
    # 步骤1：验证环境配置
    # --------------------------
    print("1/9 验证环境配置...")
    # 验证API请求头格式
    expected_headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    if headers != expected_headers:
        print("[错误] API请求头格式不符合GitHub API v3规范", file=sys.stderr)
        return False
    print("✓ 环境变量配置正确")
    print("✓ API请求头格式符合GitHub API v3规范")

    # --------------------------
    # 步骤2：验证功能分支存在性
    # --------------------------
    print(f"\n2/9 验证功能分支：{CONFIG['feature_branch']['name']}...")
    if not _check_branch_exists(
        CONFIG["feature_branch"]["name"], headers, github_org, CONFIG["target_repo"]
    ):
        print(f"[错误] 功能分支 {CONFIG['feature_branch']['name']} 未找到", file=sys.stderr)
        return False
    print(f"✓ 功能分支 {CONFIG['feature_branch']['name']} 存在")

    # --------------------------
    # 步骤3：验证标签文档完整性
    # --------------------------
    print(f"\n3/9 验证标签文档：{CONFIG['feature_branch']['doc_file']}...")
    doc_content = _get_file_content(
        branch=CONFIG["feature_branch"]["name"],
        file_path=CONFIG["feature_branch"]["doc_file"],
        headers=headers,
        org=github_org,
        repo=CONFIG["target_repo"]
    )
    if not doc_content:
        print(f"[错误] 标签文档 {CONFIG['feature_branch']['doc_file']} 未找到", file=sys.stderr)
        return False

    # 解析文档中的标签列表
    documented_labels = _parse_label_table(
        content=doc_content,
        table_header=CONFIG["doc_parsing"]["table_header"]
    )
    if len(documented_labels) < CONFIG["doc_parsing"]["min_label_count"]:
        print(f"[错误] 文档标签数量不足：实际 {len(documented_labels)} 个，需至少 {CONFIG['doc_parsing']['min_label_count']} 个", file=sys.stderr)
        return False
    print(f"✓ 标签文档存在，共包含 {len(documented_labels)} 个标签")

    # --------------------------
    # 步骤4：验证Issue创建与合规性
    # --------------------------
    print(f"\n4/9 验证Issue（关键词：{CONFIG['issue_requirements']['title_keywords']}）...")
    issue = _find_issue_by_keywords(
        title_keywords=CONFIG["issue_requirements"]["title_keywords"],
        headers=headers,
        org=github_org,
        repo=CONFIG["target_repo"]
    )
    if not issue:
        print("[错误] 未找到符合关键词的Issue", file=sys.stderr)
        return False

    issue_number = issue["number"]
    issue_body = issue.get("body", "")
    issue_labels = [label["name"] for label in issue.get("labels", [])]

    # 校验Issue必需章节
    missing_issue_sections = [
        sec for sec in CONFIG["issue_requirements"]["required_sections"] 
        if sec not in issue_body
    ]
    if missing_issue_sections:
        print(f"[错误] Issue缺失必需章节：{', '.join(missing_issue_sections)}", file=sys.stderr)
        return False

    # 校验Issue必需关键词
    missing_issue_keywords = [
        kw for kw in CONFIG["issue_requirements"]["body_keywords"] 
        if kw.lower() not in issue_body.lower()
    ]
    if missing_issue_keywords:
        print(f"[错误] Issue缺失必需关键词：{', '.join(missing_issue_keywords)}", file=sys.stderr)
        return False

    # 校验Issue初始标签
    missing_issue_labels = [
        lbl for lbl in CONFIG["issue_requirements"]["initial_labels"] 
        if lbl not in issue_labels
    ]
    if missing_issue_labels:
        print(f"[错误] Issue缺失初始必需标签：{', '.join(missing_issue_labels)}", file=sys.stderr)
        return False
    print(f"✓ Issue #{issue_number} 合规（标题：{issue['title']}）")

    # --------------------------
    # 步骤5：验证PR创建与合规性
    # --------------------------
    print(f"\n5/9 验证PR（关键词：{CONFIG['pr_requirements']['title_keywords']}）...")
    pr = _find_pr_by_keywords(
        title_keywords=CONFIG["pr_requirements"]["title_keywords"],
        headers=headers,
        org=github_org,
        repo=CONFIG["target_repo"]
    )
    if not pr:
        print("[错误] 未找到符合关键词的PR", file=sys.stderr)
        return False

    pr_number = pr["number"]
    pr_body = pr.get("body", "")
    pr_labels = pr.get("labels", [])

    # 校验PR关联Issue格式
    expected_issue_ref = CONFIG["pr_requirements"]["issue_reference_pattern"].replace("{issue_number}", str(issue_number))
    if expected_issue_ref.lower() not in pr_body.lower():
        print(f"[错误] PR未按格式关联Issue：需包含「{expected_issue_ref}」", file=sys.stderr)
        return False

    # 校验PR必需章节
    missing_pr_sections = [
        sec for sec in CONFIG["pr_requirements"]["required_sections"] 
        if sec not in pr_body
    ]
    if missing_pr_sections:
        print(f"[错误] PR缺失必需章节：{', '.join(missing_pr_sections)}", file=sys.stderr)
        return False

    # 校验PR必需关键词
    missing_pr_keywords = [
        kw for kw in CONFIG["pr_requirements"]["body_keywords"] 
        if kw.lower() not in pr_body.lower()
    ]
    if missing_pr_keywords:
        print(f"[错误] PR缺失必需关键词：{', '.join(missing_pr_keywords)}", file=sys.stderr)
        return False

    # 校验PR标签数量
    if len(pr_labels) < CONFIG["pr_requirements"]["min_labels_count"]:
        print(f"[错误] PR标签数量不足：实际 {len(pr_labels)} 个，需至少 {CONFIG['pr_requirements']['min_labels_count']} 个", file=sys.stderr)
        return False
    print(f"✓ PR #{pr_number} 合规（标题：{pr['title']}）")

    # --------------------------
    # 步骤6：验证Issue标签完整性
    # --------------------------
    print(f"\n6/9 验证Issue标签完整性（共需 {len(CONFIG['expected_labels'])} 个标签）...")
    missing_issue_all_labels = [
        lbl for lbl in CONFIG["expected_labels"] 
        if lbl not in issue_labels
    ]
    if missing_issue_all_labels:
        print(f"[错误] Issue缺失 {len(missing_issue_all_labels)} 个预期标签：{missing_issue_all_labels[:5]}...", file=sys.stderr)
        return False
    print(f"✓ Issue #{issue_number} 包含所有预期标签")

    # --------------------------
    # 步骤7：验证Issue评论合规性
    # --------------------------
    print(f"\n7/9 验证Issue评论（关联PR #{pr_number}）...")
    issue_comments = _get_issue_comments(issue_number, headers, github_org, CONFIG["target_repo"])
    valid_comment_found = False

    for comment in issue_comments:
        comment_body = comment.get("body", "").lower()
        # 1. 校验评论是否包含PR关联标识
        expected_pr_ref = CONFIG["comment_requirements"]["pr_reference_flag"].replace("{pr_number}", str(pr_number))
        if expected_pr_ref.lower() not in comment_body:
            continue
        
        # 2. 校验评论是否包含所有必需关键词
        has_all_keywords = all(
            kw.lower() in comment_body 
            for kw in CONFIG["comment_requirements"]["keywords"]
        )
        if not has_all_keywords:
            continue
        
        # 3. 校验评论是否包含所有必需内容标识
        has_all_flags = all(
            flag.lower() in comment_body 
            for flag in CONFIG["comment_requirements"]["content_flags"]
        )
        if has_all_flags:
            valid_comment_found = True
            break

    if not valid_comment_found:
        print(f"[错误] Issue #{issue_number} 未找到关联PR #{pr_number}的合规评论", file=sys.stderr)
        return False
    print(f"✓ Issue #{issue_number} 存在合规评论（关联PR #{pr_number}）")

    # --------------------------
    # 步骤8：验证标签文档与预期标签一致性
    # --------------------------
    print(f"\n8/9 验证标签文档与预期标签一致性...")
    # 检查预期标签是否全部在文档中存在
    missing_in_doc = [
        lbl for lbl in CONFIG["expected_labels"] 
        if lbl not in documented_labels
    ]
    if missing_in_doc:
        print(f"[错误] 预期标签未全部出现在文档中：{missing_in_doc[:5]}...（共缺失{len(missing_in_doc)}个）", file=sys.stderr)
        return False
    
    # 检查文档中是否存在未预期的标签
    unexpected_in_doc = [
        lbl for lbl in documented_labels 
        if lbl not in CONFIG["expected_labels"]
    ]
    if unexpected_in_doc:
        print(f"[警告] 文档中存在未预期标签：{unexpected_in_doc[:3]}...（不影响验证通过）")
    
    print(f"✓ 所有预期标签（共{len(CONFIG['expected_labels'])}个）均在文档中存在")

    # --------------------------
    # 步骤9：验证PR标签与预期标签一致性
    # --------------------------
    print(f"\n9/9 验证PR标签与预期标签一致性...")
    pr_label_names = [label["name"] for label in pr_labels]
    
    # 检查PR是否包含至少部分核心预期标签
    core_expected_labels = CONFIG["expected_labels"][:10]
    missing_pr_core_labels = [
        lbl for lbl in core_expected_labels 
        if lbl not in pr_label_names
    ]
    if len(missing_pr_core_labels) > len(core_expected_labels) // 2:
        print(f"[错误] PR #{pr_number} 缺失过多核心预期标签：{missing_pr_core_labels[:3]}...", file=sys.stderr)
        return False
    
    print(f"✓ PR #{pr_number} 核心标签合规（缺失{len(missing_pr_core_labels)}个核心标签，在允许范围内）")

    # --------------------------
    # 步骤10：验证完成
    # --------------------------
    print(f"\n9/9 所有验证步骤完成")
    print("\n" + "=" * 60)
    print("✅ 所有标签颜色标准化验证步骤通过！")
    print(f"验证对象：{github_org}/{CONFIG['target_repo']}")
    print(f"功能分支：{CONFIG['feature_branch']['name']}")
    print(f"验证Issue：#{issue_number}")
    print(f"验证PR：#{pr_number}")
    print("=" * 60)
    return True


# --------------------------
# 脚本入口
# --------------------------
if __name__ == "__main__":
    try:
        verification_result = verify_label_standardization()
        sys.exit(0 if verification_result else 1)
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 执行过程中发生未预期错误：{str(e)}")
        sys.exit(1)