export function TitleFieldTemplate({Templates, id, key, ...props}) {
    const title = Templates.TitleFieldTemplate({id, ...props})
    const info = Templates.InfoFieldTemplate ? Templates.InfoFieldTemplate({id: `${id}-info`, ...props}) : null
    return <span id={id} key={key}>{title}{info}</span>
}

export default TitleFieldTemplate