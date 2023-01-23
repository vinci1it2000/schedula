import {getUiOptions, getTemplate, descriptionId} from "@rjsf/utils";

export default function Description(
    {children, render, domain, select, ...props}) {
    const {uiSchema, registry, schema, idSchema} = render
    const uiOptions = getUiOptions(uiSchema);
    const DescriptionFieldTemplate = getTemplate('DescriptionFieldTemplate', registry, uiOptions);
    const description = children || uiOptions.description || schema.description;
    return <DescriptionFieldTemplate
        id={descriptionId(idSchema)}
        description={description}
        schema={schema}
        uiSchema={uiSchema}
        registry={registry}
        {...props}
    />
}