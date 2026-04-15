from agent.tasks.user_tasks import UserTasks


def password_reset(name: str, new_password: str) -> str:
    return UserTasks.get_password_reset_prompt(name=name, new_password=new_password)


def conditional_create_and_license(name: str, email: str, license: str) -> str:
    return UserTasks.get_conditional_create_license_prompt(name=name, email=email, license=license)


__all__ = [
    "UserTasks",
    "password_reset",
    "conditional_create_and_license",
]
