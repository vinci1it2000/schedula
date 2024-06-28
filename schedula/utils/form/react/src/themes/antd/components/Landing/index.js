import React, {useEffect} from "react";
import {getComponents} from '../../../../core';

const CoreComponent = React.lazy(() => import('./core'));

export const LandingTemplate = (
    {
        render,
        sections: {
            config = {},
            other = {},
            template = [],
            page = {},
            style = []
        },
        ...props
    }
) => {
    useEffect(() => {
        const styles = style.map(({cssString}) => {
            // Create a new style element
            const styleElement = document.createElement('style');

            // Append the CSS string to the style element
            styleElement.innerHTML = cssString;

            // Append the style element to the head of the document
            document.head.appendChild(styleElement);
            return styleElement
        })

        // Cleanup function to remove the style element when the component unmounts
        return () => {
            styles.forEach(styleElement => {
                document.head.removeChild(styleElement)
            })
        };
    }, [style]);
    const sections = template.map((id) => {
        const Element = getComponents({
            render,
            component: `Landing.${id.split('_').slice(0, -1).join('_')}`
        })
        return Element ? <Element
            id={id} key={id} dataSourceMerge render={render} {...config[id]}
        /> : null
    })
    if (other.point) {
        const Element = getComponents({
            render,
            component: `Landing.Point`
        })
        sections.push(
            <Element key={'list'} dataSourceMerge data={template}
                     render={render} {...other.point}/>
        )
    }
    return <CoreComponent {...props}>
        {sections}
    </CoreComponent>
};

const Component = ({children, render, ...props}) => {
    return <CoreComponent {...props}>
        {children}
    </CoreComponent>
};
export default Component;