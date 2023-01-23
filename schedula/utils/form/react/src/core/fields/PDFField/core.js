import {createElement} from 'react'
import {getUiOptions} from "@rjsf/utils";
import {
    Page,
    Text,
    View,
    Image,
    Document,
    Link,
    Font,
    PDFViewer,
    pdf
} from '@react-pdf/renderer';
import assign from "lodash/assign";
import get from "lodash/get";
import isObject from "lodash/isObject";
import fonts from './fonts/Roboto'
import PDFMarkdown, {mdStyles} from './PDFMarkdown'
import getStyle from './getStyle'
import './PDFViewer.css'
import debounce from "lodash/debounce";

function PDFImage({children, ...props}) {
    return <Image src={children[0]} {...props}/>
}

function PDFLink({children, ...props}) {
    return <Link src={children[0]} {...props}/>
}

function PDFPageNumber({...props}) {
    return <Text render={
        ({pageNumber, totalPages}) => {
            return `${pageNumber} / ${totalPages}`
        }
    } {...props}/>
}


const hyphenationCallback = (word) => {
    return [word]
};

Font.registerHyphenationCallback(hyphenationCallback);
var components = {
    Page,
    Text,
    View,
    Image: PDFImage,
    Document,
    Link: PDFLink,
    PageNumber: PDFPageNumber
};


var renders = {
    Markdown: PDFMarkdown
}

export function registerFont(options) {
    Font.register(options)
}

fonts.forEach(registerFont)


const defaultStyles = {
    ...mdStyles,
    page: {
        paddingTop: 35,
        paddingBottom: 65,
        paddingHorizontal: 35,
        color: "rgba(0,0,0,.88)",
        fontSize: "12px"
    },
    "left-logo": {
        width: 100,
        height: 50
    },
    "right-logo": {
        width: 100,
        height: 50
    },
    header: {
        justifyContent: "space-between",
        marginBottom: 20,
        paddingBottom: 2,
        textAlign: "center",
        color: "grey",
        flexDirection: "row",
        borderBottomWidth: 1,
        borderBottomColor: "#dbdbdb",
        borderBottomStyle: "solid",
        alignItems: "stretch"
    },
    "header-body": {
        flexDirection: "column",
        textAlign: "center",
        flexGrow: 1,
        margin: 10,
        width: 0
    },
    footer: {
        position: "absolute",
        bottom: 15,
        paddingTop: 5,
        left: 35,
        fontSize: 8,
        right: 35,
        textAlign: "center",
        borderTopWidth: 1,
        borderTopColor: "#dbdbdb",
        borderTopStyle: "solid",
        color: "grey"
    },
    pageNumber: {
        position: 'absolute',
        fontSize: 12,
        bottom: 30,
        left: 0,
        right: 0,
        textAlign: 'center',
        color: 'grey',
    },
    "heading-2": {
        fontSize: 12,
        paddingTop: 3,
        fontWeight: "bold",
        textAlign: "left",
        backgroundColor: "#dbdbdb",
        color: "#363636",
        padding: 6,
        marginBottom: 10
    },
    title: {
        fontSize: 16,
        textAlign: "center",
        paddingBottom: 20
    },
    subtitle: {
        fontSize: 12,
        paddingTop: 3,
        textAlign: "left"
    },
    field: {
        view: {
            flexGrow: 1,
            flexDirection: "row",
            paddingBottom: 5
        },
        text: {
            width: "50%"
        },
        title: {
            width: "50%",
            fontWeight: "bold"
        }
    },
    "field-1": {
        view: {
            flexGrow: 1,
            flexDirection: "row",
            paddingBottom: 5
        },
        text: {
            width: "70%"
        },
        title: {
            width: "30%",
            fontWeight: "bold"
        }
    },
    bold: {
        fontWeight: "bold"
    },
    paragraph: {
        lineHeight: 1.6,
        paddingBottom: 10,
        textAlign: "justify"
    }
};


function createPDFElement({
                              key,
                              element,
                              settings,
                              formData,
                              activeSections,
                              ...parentProps
                          }) {
    if (isObject(element)) {
        const {section} = element
        const {sections, styles} = settings
        if (section && !activeSections.includes(section)) {
            return null
        }
        const {
            component = "Text",
            style,
            path,
            props: rawProps = {},
            children: rawChildren = []
        } = (section ? assign({}, get(sections, section, {}), element) : element);
        const {style: propsStyle, transformData, ...baseProps} = rawProps
        const props = assign({key}, baseProps, {style: getStyle([style, propsStyle], styles)})
        let children;
        if (renders.hasOwnProperty(component)) {
            return renders[component]({
                ...parentProps,
                key,
                children: rawChildren,
                formData,
                settings,
                transformData,
                props
            })
        } else {
            children = (path ? [get(formData, path)] : (rawChildren || []).map((child, index) => {
                return createPDFElement({
                    ...parentProps,
                    key: `${key}-${index}`,
                    formData,
                    element: child,
                    settings,
                    activeSections
                })
            }))
        }
        children = children.filter(v => v !== null)
        if (children.length) {
            return createElement(components[component], props, children)
        } else {
            return createElement(components[component], props)
        }
    } else {
        return element
    }
}

export function generatePDF({
                                idSchema,
                                uiSchema,
                                formData,
                                activeSections,
                                ...props
                            }) {
    const {
        styles: rawStyles, sections, document = []
    } = getUiOptions(uiSchema);
    if (!activeSections) {
        activeSections = Object.keys(sections)
    }
    const styles = assign({}, defaultStyles, rawStyles)
    return createPDFElement({
        ...props,
        key: idSchema.$id,
        element: {
            component: "Document", children: document
        },
        settings: {styles, sections},
        formData,
        activeSections
    })
}

const renderPDF = debounce((idSchema, uiSchema, formData, permanentSections, validSections, setUrl, props) => {
    pdf(generatePDF({
        ...props,
        idSchema,
        uiSchema,
        formData,
        activeSections: [...permanentSections, ...validSections],
    })).toBlob().then(blob => {
        setUrl(URL.createObjectURL(blob))
    })
}, 500)
export {renderPDF}
export default function PDFField({idSchema, uiSchema, formData, ...props}) {
    const {styles, sections, document, ...viewerProps} = getUiOptions(uiSchema)
    return <PDFViewer
        className={'pdf-viewer'} key={idSchema.$id} width={'100%'}
        height={'300px'} {...viewerProps}>
        {generatePDF({idSchema, uiSchema, formData, ...props})}
    </PDFViewer>
}
