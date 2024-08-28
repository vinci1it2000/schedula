import React, {useEffect, useState, forwardRef} from "react";

function convertToHeightWidthTopLeft(
    {height, width, bottom, top, right, left},
    containerDimensions = {width: window.innerWidth, height: window.innerHeight}
) {
    const result = {};

    if (typeof height === 'string' && height.endsWith('%')) {
        result.height = parseFloat(height.slice(0, -1)) / 100 * containerDimensions.height;
    } else if (height !== undefined) {
        result.height = height;
    } else if (bottom !== undefined && top !== undefined) {
        result.height = containerDimensions.height - bottom - top;
    } else {
        result.height = containerDimensions.height;
    }

    if (typeof width === 'string' && width.endsWith('%')) {
        result.width = parseFloat(width.slice(0, -1)) / 100 * containerDimensions.width;
    } else if (width !== undefined) {
        result.width = width;
    } else if (right !== undefined && left !== undefined) {
        result.width = containerDimensions.width - right - left;
    } else {
        result.width = containerDimensions.width;
    }

    if (top !== undefined) {
        result.top = window.screenY + top;
    } else if (bottom !== undefined) {
        result.top = window.screenY + containerDimensions.height - bottom - result.height;
    } else {
        result.top = window.screenY
    }

    if (left !== undefined) {
        result.left = window.screenX + left;
    } else if (right !== undefined) {
        result.left = window.screenX + containerDimensions.width - right - result.width;
    } else {
        result.left = window.screenX
    }

    return result;
}


const StripePortal = forwardRef((
    {
        children,
        render: {formContext: {form}},
        urlPortalSession,
        height,
        width,
        top,
        bottom,
        left,
        right,
        ...props
    }, ref
) => {
    const [popup, setPopup] = useState()
    const [open, setOpen] = useState(false);
    const {state: {language, userInfo: {id: user_id = null}}} = form

    useEffect(() => {
        if (open) {
            if (popup) {
                popup.focus()
            } else if (user_id) {
                form.setState({loading: true}, () => {
                    form.postData({
                        url: urlPortalSession,
                        data: {
                            locale: language.replace('_', '-').split('-')[0]
                        },
                    }, ({data: {session_url}}) => {
                        form.setState({loading: false})
                        const {
                                width: popWidth,
                                height: popHeight,
                                top: popTop,
                                left: popLeft
                            } = convertToHeightWidthTopLeft({
                                height, width, top, bottom, left, right
                            }),
                            params = `status=no,location=no,toolbar=no,menubar=no,width=${popWidth},height=${popHeight},left=${popLeft},top=${popTop}`;
                        const popup = window.open(session_url, '_blank', params);
                        setPopup(popup)
                    }, () => {
                        form.setState({loading: false})
                    })
                })
            }
        } else if (popup) {
            popup.close()
        }
    }, [open, urlPortalSession, form, language, user_id])
    useEffect(() => {
        if (popup) {
            const bringToFront = setInterval(() => {
                if (!popup || popup.closed) {
                    setPopup(null)
                    setOpen(false)
                    clearInterval(bringToFront);
                }
            }, 500);
        }
    }, [popup])
    return <div key="stripe-portal" ref={ref} onClick={() => {
        setOpen((open) => {
            if (open && popup)
                popup.focus()
            return true
        })
    }} {...props}>
        {children}
    </div>
});

export default StripePortal;