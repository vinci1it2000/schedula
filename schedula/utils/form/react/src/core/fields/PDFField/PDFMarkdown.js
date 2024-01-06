import {Image, Link, Text, View} from "@react-pdf/renderer";
import ReactMarkdown from "react-markdown";
import formatMd from "../../utils/Markdown";
import remarkGfm from "remark-gfm";
import getStyle from './getStyle'
import get from 'lodash/get'
import _ from 'lodash'

const mdStyles = {
    h1: {
        fontFamily: "Roboto",
        fontWeight: 'bold',
        marginBottom: "7px",
        color: "rgba(0,0,0,.88)",
        fontSize: "38px"
    },
    h2: {
        fontFamily: "Roboto",
        fontWeight: 'bold',
        marginTop: "16.8px",
        marginBottom: "7px",
        color: "rgba(0,0,0,.88)",
        fontSize: "30px"
    },
    h3: {
        fontFamily: "Roboto",
        fontWeight: 'bold',
        marginTop: "16.8px",
        marginBottom: "7px",
        color: "rgba(0,0,0,.88)",
        fontSize: "24px"
    },
    h4: {
        fontFamily: "Roboto",
        fontWeight: 'bold',
        marginTop: "16.8px",
        marginBottom: "7px",
        color: "rgba(0,0,0,.88)",
        fontSize: "20px"
    },
    h5: {
        fontFamily: "Roboto",
        fontWeight: 'bold',
        marginTop: "16.8px",
        marginBottom: "7px",
        color: "rgba(0,0,0,.88)",
        fontSize: "16px"
    },
    h6: {
        fontFamily: "Roboto",
        fontWeight: 'bold',
        marginTop: "16.8px",
        marginBottom: "7px",
        color: "rgba(0,0,0,.88)",
        fontSize: "14px"
    },
    p: {
        padding: 0,
        fontFamily: "Roboto",
        marginBottom: "14px",
        color: "rgba(0,0,0,.88)",
        textAlign: 'justify',
    },
    em: {
        fontFamily: "Roboto-Italic"
    },
    strong: {
        fontWeight: 'bold'
    },
    a: {
        color: "#1677ff"
    },
    img: {
        marginVertical: "15px",
        width: "300px",
        height: '100px',
        textAlign: "center",
    },
    blockquote: {
        marginVertical: "20px",
        marginHorizontal: "10px",
        paddingVertical: "7px",
        paddingHorizontal: "10px",
        backgroundColor: "#f9f9f9",
        borderLeftColor: "#ccc",
        borderLeftStyle: "solid",
        borderLeftWidth: "10px"
    },
    hr: {
        marginVertical: "7px",
        padding: 0,
        borderTopColor: "#ccc",
        borderTopStyle: "solid",
        borderTopWidth: "1px"
    },
    br: {
        marginVertical: "7px",
        padding: 0,
    },
    ol: {
        marginLeft: '7px',
        marginBottom: "14px"
    },
    ul: {
        marginLeft: '7px',
        marginBottom: "14px"
    },
    li: {
        marginBottom: 0
    },
    table: {
        display: "flex",
        flexDirection: "column",
        width: "auto",
        textAlign: "center"
    },
    thead: {
        flexDirection: "row",
        display: "flex",
        textAlign: "center",
        backgroundColor: "rgb(250, 250, 250)",
        paddingTop: 3
    },
    tr: {
        width: "100%",
        display: "flex",
        textAlign: "center",
        margin: 0,
        padding: "7px",
        flexDirection: "row",
        borderBottomWidth: 1,
        borderBottomColor: "rgb(240, 240, 240)",
        borderBottomStyle: "solid"
    },
    th: {
        fontWeight: 'bold',
        margin: 0,
        textAlign: "center",
        flex: 1,
        borderRightWidth: "2px",
        borderRightColor: "rgb(240, 240, 240)",
        borderRightStyle: "solid"
    },
    td: {
        flex: 1,
        margin: 0,
        textAlign: "center"
    },
    tbody: {}
}
export {mdStyles}

export default function PDFMarkdown(
    {children, formData, key, settings, formContext, transformData, ...props}) {
    const {form} = formContext
    const {styles} = settings
    if (transformData) {
        formData = form.compileFunc(transformData)({
            data: _.cloneDeep(formData), _
        })
    }
    return <ReactMarkdown
        key={key}
        children={formatMd({children, formData, formContext, form, ...props})}
        remarkPlugins={[remarkGfm]}
        components={{
            h1: ({children}) => (
                <Text style={getStyle('h1', styles)}>{children}</Text>
            ),
            h2: ({children}) => (
                <Text style={getStyle('h2', styles)}>{children}</Text>
            ),
            h3: ({children}) => (
                <Text style={getStyle('h3', styles)}>{children}</Text>
            ),
            h4: ({children}) => (
                <Text style={getStyle('h4', styles)}>{children}</Text>
            ),
            h5: ({children}) => (
                <Text style={getStyle('h5', styles)}>{children}</Text>
            ),
            h6: ({children}) => (
                <Text style={getStyle('h6', styles)}>{children}</Text>
            ),
            p: ({children}) => {
                if (Array.isArray(children) && children.every(v => (typeof v === 'string' && (v === '\n' || v === '\\')) || get(v, 'props.node.tagName') === 'br'))
                    return children.map(v => (typeof v === 'string' && v === '\\' ?
                        <Text style={getStyle('br', styles)}/> : v))
                return <Text style={getStyle('p', styles)}>{children}</Text>
            },
            em: ({children}) => (
                <Text style={getStyle('em', styles)}>{children}</Text>
            ),
            strong: ({children}) => (
                <Text style={getStyle('strong', styles)}>{children}</Text>
            ),
            a: ({children, href}) => (
                <Link style={getStyle('a', styles)} src={href}>{children}</Link>
            ),
            img: ({alt, src}) => (
                <Image style={getStyle(['img', alt], styles)} src={src}/>
            ),
            blockquote: ({children}) => (
                <View style={getStyle('blockquote', styles)}>{children}</View>
            ),
            ol: ({children}) => {
                return <View style={getStyle('ol', styles)}>
                    {children.filter(v => v !== '\n').map((child, index) => {
                        return <Text key={index}
                                     style={getStyle(['p', 'li'], styles)}>
                            {index + 1}. {child}
                        </Text>
                    })}
                </View>
            },
            ul: ({children}) => {
                return <View style={getStyle('ol', styles)}>
                    {children.filter(v => v !== '\n').map((child, index) => {
                        return <Text key={index}
                                     style={getStyle(['p', 'li'], styles)}>
                            {'•'} {child}
                        </Text>
                    })}
                </View>
            },
            li: ({children}) => (
                <Text style={getStyle(['p', 'li'], styles)}>{children}</Text>
            ),
            hr: () => (<View style={getStyle('hr', styles)}/>),
            table: ({children}) => (
                <View style={getStyle('table', styles)}>{children}</View>
            ),
            tbody: ({children}) => (
                <View style={getStyle('tbody', styles)}>{children}</View>
            ),
            td: ({children, style}) => (
                <Text style={getStyle(['p', 'td', style], styles)}>
                    {children}
                </Text>),
            th: ({children, style}) => (
                <Text style={getStyle(['p', 'th', style], styles)}>
                    {children}
                </Text>),
            thead: ({children}) => (
                <View style={getStyle('thead', styles)}>{children}</View>
            ),
            tr: ({children}) => (
                <View style={getStyle('tr', styles)}>{children}</View>
            ),
            br: () => (
                <Text style={getStyle('br', styles)}/>
            )
        }}/>
};