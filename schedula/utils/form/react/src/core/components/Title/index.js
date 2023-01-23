import {getUiOptions, getTemplate, titleId} from "@rjsf/utils";

export default function Title(
    {children, render, domain, select, ...props}) {
    const {uiSchema, registry, required, schema, parent, idSchema} = render
    const uiOptions = getUiOptions(uiSchema);
    const TitleFieldTemplate = getTemplate('TitleFieldTemplate', registry, uiOptions);
    const title = children || uiOptions.title || (schema.title === undefined ? parent.props.name : schema.title);
    return <TitleFieldTemplate
        id={titleId(idSchema)}
        title={title}
        required={required}
        schema={schema}
        uiSchema={uiSchema}
        registry={registry}
        {...props}
    />
}