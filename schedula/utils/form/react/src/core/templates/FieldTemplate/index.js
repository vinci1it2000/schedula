import {getUiOptions} from "@rjsf/utils";


export function FieldTemplate(
    {Templates, schema, uiSchema, displayLabel, children, ...props}
) {
    const {label = false, onlyChildren = false} = getUiOptions(uiSchema)
    if (!displayLabel) {
        displayLabel = label | ""
    }
    if (onlyChildren) {
        return children
    }
    return Templates.FieldTemplate({
        schema,
        uiSchema,
        displayLabel,
        children,
        ...props
    })
}

export default FieldTemplate