from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import IngredientCategory, Unit, User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


# Seed data: (name, category, default_unit)
_SEED_INGREDIENTS: list[tuple[str, IngredientCategory, Unit]] = [
    # Produce
    ("onion", IngredientCategory.PRODUCE, Unit.PIECE),
    ("garlic", IngredientCategory.PRODUCE, Unit.CLOVE),
    ("tomato", IngredientCategory.PRODUCE, Unit.PIECE),
    ("carrot", IngredientCategory.PRODUCE, Unit.PIECE),
    ("potato", IngredientCategory.PRODUCE, Unit.PIECE),
    ("bell pepper", IngredientCategory.PRODUCE, Unit.PIECE),
    ("spinach", IngredientCategory.PRODUCE, Unit.GRAM),
    ("lettuce", IngredientCategory.PRODUCE, Unit.PIECE),
    ("broccoli", IngredientCategory.PRODUCE, Unit.PIECE),
    ("zucchini", IngredientCategory.PRODUCE, Unit.PIECE),
    ("mushrooms", IngredientCategory.PRODUCE, Unit.GRAM),
    ("cucumber", IngredientCategory.PRODUCE, Unit.PIECE),
    ("lemon", IngredientCategory.PRODUCE, Unit.PIECE),
    ("lime", IngredientCategory.PRODUCE, Unit.PIECE),
    ("apple", IngredientCategory.PRODUCE, Unit.PIECE),
    ("banana", IngredientCategory.PRODUCE, Unit.PIECE),
    ("orange", IngredientCategory.PRODUCE, Unit.PIECE),
    ("celery", IngredientCategory.PRODUCE, Unit.PIECE),
    ("leek", IngredientCategory.PRODUCE, Unit.PIECE),
    ("avocado", IngredientCategory.PRODUCE, Unit.PIECE),
    # Dairy
    ("milk", IngredientCategory.DAIRY, Unit.MILLILITER),
    ("butter", IngredientCategory.DAIRY, Unit.GRAM),
    ("eggs", IngredientCategory.DAIRY, Unit.PIECE),
    ("cheddar cheese", IngredientCategory.DAIRY, Unit.GRAM),
    ("parmesan", IngredientCategory.DAIRY, Unit.GRAM),
    ("mozzarella", IngredientCategory.DAIRY, Unit.GRAM),
    ("yogurt", IngredientCategory.DAIRY, Unit.GRAM),
    ("heavy cream", IngredientCategory.DAIRY, Unit.MILLILITER),
    ("sour cream", IngredientCategory.DAIRY, Unit.GRAM),
    # Meat
    ("chicken breast", IngredientCategory.MEAT, Unit.GRAM),
    ("chicken thigh", IngredientCategory.MEAT, Unit.GRAM),
    ("ground beef", IngredientCategory.MEAT, Unit.GRAM),
    ("beef steak", IngredientCategory.MEAT, Unit.GRAM),
    ("pork chop", IngredientCategory.MEAT, Unit.GRAM),
    ("bacon", IngredientCategory.MEAT, Unit.GRAM),
    ("sausage", IngredientCategory.MEAT, Unit.PIECE),
    ("ham", IngredientCategory.MEAT, Unit.GRAM),
    # Seafood
    ("salmon", IngredientCategory.SEAFOOD, Unit.GRAM),
    ("tuna", IngredientCategory.SEAFOOD, Unit.GRAM),
    ("shrimp", IngredientCategory.SEAFOOD, Unit.GRAM),
    ("cod", IngredientCategory.SEAFOOD, Unit.GRAM),
    # Grains
    ("rice", IngredientCategory.GRAINS, Unit.GRAM),
    ("pasta", IngredientCategory.GRAINS, Unit.GRAM),
    ("all-purpose flour", IngredientCategory.GRAINS, Unit.GRAM),
    ("oats", IngredientCategory.GRAINS, Unit.GRAM),
    ("breadcrumbs", IngredientCategory.GRAINS, Unit.GRAM),
    ("quinoa", IngredientCategory.GRAINS, Unit.GRAM),
    ("couscous", IngredientCategory.GRAINS, Unit.GRAM),
    # Pantry
    ("olive oil", IngredientCategory.PANTRY, Unit.MILLILITER),
    ("vegetable oil", IngredientCategory.PANTRY, Unit.MILLILITER),
    ("salt", IngredientCategory.PANTRY, Unit.GRAM),
    ("sugar", IngredientCategory.PANTRY, Unit.GRAM),
    ("baking powder", IngredientCategory.PANTRY, Unit.TEASPOON),
    ("baking soda", IngredientCategory.PANTRY, Unit.TEASPOON),
    ("white vinegar", IngredientCategory.PANTRY, Unit.MILLILITER),
    ("soy sauce", IngredientCategory.PANTRY, Unit.MILLILITER),
    ("honey", IngredientCategory.PANTRY, Unit.TABLESPOON),
    ("tomato paste", IngredientCategory.PANTRY, Unit.TABLESPOON),
    ("canned tomatoes", IngredientCategory.PANTRY, Unit.CAN),
    ("chicken broth", IngredientCategory.PANTRY, Unit.MILLILITER),
    ("vegetable broth", IngredientCategory.PANTRY, Unit.MILLILITER),
    ("black pepper", IngredientCategory.PANTRY, Unit.GRAM),
    ("dijon mustard", IngredientCategory.PANTRY, Unit.TABLESPOON),
    ("maple syrup", IngredientCategory.PANTRY, Unit.TABLESPOON),
    # Spices
    ("cumin", IngredientCategory.SPICES, Unit.TEASPOON),
    ("paprika", IngredientCategory.SPICES, Unit.TEASPOON),
    ("oregano", IngredientCategory.SPICES, Unit.TEASPOON),
    ("basil", IngredientCategory.SPICES, Unit.TEASPOON),
    ("thyme", IngredientCategory.SPICES, Unit.TEASPOON),
    ("rosemary", IngredientCategory.SPICES, Unit.TEASPOON),
    ("cinnamon", IngredientCategory.SPICES, Unit.TEASPOON),
    ("turmeric", IngredientCategory.SPICES, Unit.TEASPOON),
    ("garlic powder", IngredientCategory.SPICES, Unit.TEASPOON),
    ("onion powder", IngredientCategory.SPICES, Unit.TEASPOON),
    ("curry powder", IngredientCategory.SPICES, Unit.TEASPOON),
    ("chili powder", IngredientCategory.SPICES, Unit.TEASPOON),
    ("red pepper flakes", IngredientCategory.SPICES, Unit.TEASPOON),
    ("nutmeg", IngredientCategory.SPICES, Unit.TEASPOON),
    # Bakery
    ("bread", IngredientCategory.BAKERY, Unit.SLICE),
    ("flour tortilla", IngredientCategory.BAKERY, Unit.PIECE),
    ("pita bread", IngredientCategory.BAKERY, Unit.PIECE),
    # Frozen
    ("frozen peas", IngredientCategory.FROZEN, Unit.GRAM),
    ("frozen corn", IngredientCategory.FROZEN, Unit.GRAM),
]


def _seed_ingredients(session: Session) -> None:
    """Insert seed ingredients that are not yet in the database."""
    for name, category, default_unit in _SEED_INGREDIENTS:
        existing = crud.get_ingredient_by_name(session=session, name=name)
        if not existing:
            from app.models import IngredientCreate

            crud.create_ingredient(
                session=session,
                ingredient_in=IngredientCreate(
                    name=name, category=category, default_unit=default_unit
                ),
            )


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    _seed_ingredients(session)
