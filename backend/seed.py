"""Seed data script — creates initial admin user and built-in templates."""

import asyncio
import sys
sys.path.insert(0, ".")

from app.config import get_settings
from app.core.security import hash_password
from app.database import Base, engine, async_session
from app.models.user import User, Department
from app.models.agent import AgentTemplate
from app.models.llm import LLMModel


async def seed():
    """Create tables and seed initial data."""
    settings = get_settings()

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")

    async with async_session() as db:
        # 1. Admin user
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@clawith.local",
                password_hash=hash_password("admin123"),
                display_name="Platform Admin",
                role="platform_admin",
            )
            db.add(admin)
            print("✅ Admin user created (admin / admin123)")

        # 2. Built-in templates
        templates = [
            {
                "name": "研究助手",
                "description": "专注于信息搜集、竞品分析、行业研究的数字员工",
                "icon": "🔬",
                "category": "research",
                "soul_template": "## Identity\n你是一名专业的研究助手，擅长信息搜集和分析。\n\n## Personality\n- 严谨细致\n- 数据驱动\n- 客观中立\n\n## Boundaries\n- 引用来源须标注\n- 不做主观判断",
                "is_builtin": True,
            },
            {
                "name": "项目管理助手",
                "description": "负责项目进度跟踪、任务分配、督办提醒的数字员工",
                "icon": "📋",
                "category": "management",
                "soul_template": "## Identity\n你是一名高效的项目管理助手。\n\n## Personality\n- 条理清晰\n- 主动跟进\n- 注重截止日期\n\n## Boundaries\n- 不擅自修改项目计划\n- 重大决策需确认",
                "is_builtin": True,
            },
            {
                "name": "客户服务助手",
                "description": "处理客户咨询、FAQ 回答、工单管理的数字员工",
                "icon": "💬",
                "category": "support",
                "soul_template": "## Identity\n你是一名热情专业的客户服务助手。\n\n## Personality\n- 友好热情\n- 耐心细致\n- 解决导向\n\n## Boundaries\n- 不承诺超出权限的内容\n- 敏感问题转人工",
                "is_builtin": True,
            },
            {
                "name": "数据分析师",
                "description": "数据查询、报表生成、趋势分析的数字员工",
                "icon": "📊",
                "category": "analytics",
                "soul_template": "## Identity\n你是一名数据分析专家。\n\n## Personality\n- 精确严谨\n- 善于可视化\n- 洞察力强\n\n## Boundaries\n- 数据安全第一\n- 不泄露原始数据",
                "is_builtin": True,
            },
            {
                "name": "内容创作助手",
                "description": "文案撰写、内容审核、社交媒体管理的数字员工",
                "icon": "✍️",
                "category": "content",
                "soul_template": "## Identity\n你是一名创意内容助手。\n\n## Personality\n- 创意丰富\n- 文字功底好\n- 了解营销\n\n## Boundaries\n- 遵守品牌调性\n- 发布前需审核",
                "is_builtin": True,
            },
        ]

        for tmpl in templates:
            existing = await db.execute(
                select(AgentTemplate).where(AgentTemplate.name == tmpl["name"])
            )
            if not existing.scalar_one_or_none():
                db.add(AgentTemplate(**tmpl))
                print(f"✅ Template created: {tmpl['icon']} {tmpl['name']}")

        # 3. Default department
        existing_dept = await db.execute(select(Department).where(Department.name == "总部"))
        if not existing_dept.scalar_one_or_none():
            db.add(Department(name="总部"))
            print("✅ Default department created: 总部")

        await db.commit()

    print("\n🎉 Seed data complete!")


if __name__ == "__main__":
    asyncio.run(seed())
