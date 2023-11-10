import BaseTweenOne from 'rc-tween-one';

const TweenOne = ({children, render, ...props}) => (
    <BaseTweenOne {...props}>
        {children}
    </BaseTweenOne>);
export default TweenOne;