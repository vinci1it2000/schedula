import React from 'react';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import BannerAnim, {Element} from 'rc-banner-anim';
import TweenOne from 'rc-tween-one';
import QueueAnim from 'rc-queue-anim';
import {getChildrenToRender} from './utils';
import 'rc-banner-anim/assets/index.css';

class Teams extends React.PureComponent {
    getChildrenToRender = (children) => {
        return children.map((item, i) => {
            const {titleWrapper, ...elementPros} = item;
            return (
                <Element
                    {...elementPros}
                    key={i.toString()}
                    prefixCls={elementPros.className}
                >
                    <QueueAnim
                        type={['bottom', 'top']}
                        delay={200}
                        key="text"
                        {...titleWrapper}
                    >
                        {titleWrapper.children.map(getChildrenToRender)}
                    </QueueAnim>
                </Element>
            );
        });
    };

    render() {
        const {...tagProps} = this.props;
        const {dataSource, isMobile} = tagProps;
        delete tagProps.dataSource;
        delete tagProps.isMobile;
        return (
            <div {...tagProps} {...dataSource.wrapper}>
                <OverPack {...dataSource.OverPack}>
                    <TweenOne
                        key="wrapper"
                        animation={
                            isMobile
                                ? {
                                    scaleY: '+=0.3',
                                    opacity: 0,
                                    type: 'from',
                                    ease: 'easeOutQuad',
                                }
                                : {
                                    y: '+=30',
                                    opacity: 0,
                                    type: 'from',
                                    ease: 'easeOutQuad',
                                }
                        }
                        resetStyle
                        component=""
                    >
                        <BannerAnim
                            type="across"
                            arrow={false}
                            dragPlay={!!isMobile}
                            {...dataSource.BannerAnim}
                        >
                            {this.getChildrenToRender(dataSource.BannerAnim.children)}
                        </BannerAnim>
                    </TweenOne>
                </OverPack>
            </div>
        );
    }
}

export default Teams;
