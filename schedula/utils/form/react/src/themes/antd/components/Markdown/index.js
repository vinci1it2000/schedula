import ReactAntdown from 'react-antdown'
import formatMd from '../../../../core/utils/Markdown'
import remarkGfm from 'remark-gfm'

export default function Markdown({children, render, ...props}) {
    return <ReactAntdown
        components={{
            a: ({
                    node, href, children, ...props
                }) => <a href={href} target="_blank"
                         rel="noopener noreferrer" {...props}>{children}</a>,
        }}
        remarkPlugins={[remarkGfm]}
        urlTransform={uri => uri}>
        {formatMd({
            children, formData: render.formData, ...props
        })}
    </ReactAntdown>
}