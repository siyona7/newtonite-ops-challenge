"""
Seed script to populate the database with test data.
Creates teams, users, and 50,000 operational items.
Run after database is up and migrations are applied.
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User, TeamMember, Role
from app.models.team import Team
from app.models.item import Item, ItemType, Priority, Status
from app.models.event import Event, EventType


# Sample data for realistic seeding
TEAM_NAMES = [
    "Operations", "Engineering", "Product", "Security", "Compliance",
    "Customer Support", "Finance", "Infrastructure", "DevOps", "QA"
]

USER_NAMES = [
    "Alice Chen", "Bob Smith", "Carol Davis", "David Kim", "Eva Martinez",
    "Frank Wilson", "Grace Lee", "Henry Taylor", "Ivy Patel", "Jack Brown",
    "Karen White", "Leo Garcia", "Mia Johnson", "Noah Rodriguez", "Olivia Martinez"
]

ITEM_TITLES = [
    "Server outage in us-east-1", "Payment gateway timeout", "Customer login failure",
    "SSL certificate expiring", "Database connection pool exhausted", "API rate limit exceeded",
    "Memory leak in worker process", "Disk space warning on production", "Slow query on orders table",
    "Authentication service degraded", "Cache invalidation failed", "Message queue backlog",
    "CDN propagation delay", "Third-party API returning 500", "Scheduled maintenance window",
    "Security patch required", "Compliance audit finding", "Data retention policy violation",
    "Backup verification failed", "Load balancer misconfiguration"
]

ITEM_DESCRIPTIONS = [
    "Needs immediate attention from the team",
    "Investigating root cause",
    "Waiting for vendor response",
    "Scheduled for next release",
    "Requires approval from lead",
    "Blocked by dependency",
    "Monitoring for recurrence",
    "Documentation update needed",
    "Testing in staging environment",
    "Production fix deployed"
]


async def create_teams(session: AsyncSession, count: int = 5) -> list[uuid.UUID]:
    """Create teams and return their IDs."""
    team_ids = []
    for i in range(count):
        team = Team(name=TEAM_NAMES[i % len(TEAM_NAMES)])
        session.add(team)
        await session.flush()
        team_ids.append(team.id)
    await session.commit()
    print(f"Created {count} teams")
    return team_ids


async def create_users(session: AsyncSession, team_ids: list[uuid.UUID], count: int = 15) -> list[uuid.UUID]:
    """Create users and assign them to teams."""
    user_ids = []
    for i in range(count):
        user = User(
            email=f"user{i}@example.com",
            name=USER_NAMES[i % len(USER_NAMES)]
        )
        session.add(user)
        await session.flush()
        user_ids.append(user.id)

        # Assign each user to 1-3 teams
        assigned_teams = random.sample(team_ids, k=random.randint(1, min(3, len(team_ids))))
        for team_id in assigned_teams:
            member = TeamMember(
                user_id=user.id,
                team_id=team_id,
                role=random.choice(list(Role))
            )
            session.add(member)

    await session.commit()
    print(f"Created {count} users with team memberships")
    return user_ids


async def create_items_batch(
    session: AsyncSession,
    team_ids: list[uuid.UUID],
    user_ids: list[uuid.UUID],
    batch_size: int = 1000,
    total_count: int = 50000
) -> None:
    """Create items in batches to avoid memory issues."""
    item_types = list(ItemType)
    priorities = list(Priority)
    statuses = list(Status)

    created = 0
    while created < total_count:
        batch_count = min(batch_size, total_count - created)
        items = []

        for _ in range(batch_count):
            # Random date within the last 90 days
            created_at = datetime.utcnow() - timedelta(
                days=random.randint(0, 90),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )

            item = Item(
                team_id=random.choice(team_ids),
                owner_id=random.choice(user_ids) if random.random() > 0.1 else None,  # 10% unclaimed
                type=random.choice(item_types),
                title=random.choice(ITEM_TITLES),
                description=random.choice(ITEM_DESCRIPTIONS),
                priority=random.choice(priorities),
                status=random.choice(statuses),
                version=random.randint(1, 5),
                metadata={"source": "seed", "batch": created // batch_size},
                created_at=created_at,
                updated_at=created_at,
            )
            items.append(item)

        session.add_all(items)
        await session.commit()
        created += batch_count
        print(f"Created {created}/{total_count} items...")

    print(f"Created {total_count} items")


async def create_events_sample(session: AsyncSession, item_ids: list[uuid.UUID], user_ids: list[uuid.UUID]) -> None:
    """Create a sample of events for some items (not all 50k to save time)."""
    event_types = list(EventType)
    sample_size = min(1000, len(item_ids))  # Create events for 1000 items

    for i in range(sample_size):
        item_id = item_ids[i]
        # Create 1-3 events per item
        for _ in range(random.randint(1, 3)):
            event = Event(
                item_id=item_id,
                event_type=random.choice(event_types),
                actor_id=random.choice(user_ids),
                old_values={"status": "open"} if random.random() > 0.5 else None,
                new_values={"status": random.choice(list(Status))},
                description=f"Event {i}",
            )
            session.add(event)

    await session.commit()
    print(f"Created sample events for {sample_size} items")


async def get_item_ids(session: AsyncSession, limit: int = 1000) -> list[uuid.UUID]:
    """Get a sample of item IDs for event creation."""
    result = await session.execute(select(Item.id).limit(limit))
    return [row[0] for row in result.all()]


async def main():
    """Main seeding function."""
    print("Starting database seeding...")

    async with AsyncSessionLocal() as session:
        # Create teams
        team_ids = await create_teams(session, count=5)

        # Create users
        user_ids = await create_users(session, team_ids, count=15)

        # Create 50,000 items in batches
        await create_items_batch(session, team_ids, user_ids, batch_size=1000, total_count=50000)

        # Get sample item IDs and create events
        item_ids = await get_item_ids(session, limit=1000)
        await create_events_sample(session, item_ids, user_ids)

    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
