import ReactMarkdown from 'react-markdown'
import formatMd from '../../utils/Markdown'
import remarkGfm from 'remark-gfm'

export default function MarkdownWidget(
    {value, options, formContext, ...props}) {
    return <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={uri => {
            return uri
        }}>
        {formatMd({
            children: options.markdown || "{{ data }}",
            formData: value, ...props
        })}
    </ReactMarkdown>
}

