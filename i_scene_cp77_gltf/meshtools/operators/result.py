def finish_operator(operator, result):
    if result.message:
        operator.report({result.severity}, result.message)
    return result.blender_status
