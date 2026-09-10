from app.models.entities import Role


def test_role_name_is_tenant_scoped_in_orm():
    column = Role.__table__.c.name
    assert not column.unique

    indexes = {index.name: index for index in Role.__table__.indexes}
    assert indexes["uq_roles_global_name"].unique
    assert indexes["uq_roles_tenant_name"].unique

    assert str(indexes["uq_roles_global_name"].dialect_options["postgresql"]["where"]) == "tenant_id IS NULL"
    assert str(indexes["uq_roles_tenant_name"].dialect_options["postgresql"]["where"]) == "tenant_id IS NOT NULL"
