import React, {useCallback, forwardRef} from "react";


const StripePortal = forwardRef((
    {
        children,
        render: {formContext: {form}},
        urlPortalSession,
        ...props
    }, ref
) => {
    const {state: {language, userInfo: {id: user_id = null}}} = form
    const {location: {href: return_url}} = window
    const onClick = useCallback(() => {
        if (user_id) {
            form.setState({loading: true}, () => {
                form.postData({
                    url: urlPortalSession,
                    data: {
                        return_url,
                        locale: language.replace('_', '-').split('-')[0]
                    },
                }, ({data: {session_url}}) => {
                    form.setState({loading: false})
                    window.location.href = session_url
                }, () => {
                    form.setState({loading: false})
                })
            })
        }
    }, [urlPortalSession, return_url, form, language, user_id])

    return <div key="stripe-portal" ref={ref} onClick={onClick} {...props}>
        {children}
    </div>
});

export default StripePortal;