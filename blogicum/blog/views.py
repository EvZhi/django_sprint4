from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.base import Model as Model
from django.views.generic import (
    CreateView, DetailView, DeleteView, ListView, UpdateView
)
from django.shortcuts import get_object_or_404, get_list_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from blog.models import Category, Comments, Post
from blog.forms import CommentsForm, PostForm

PUGINATION_NUMBER = 10


class OnlyAuthorMixin(UserPassesTestMixin):

    def test_func(self):
        object = self.get_object()
        return object.author == self.request.user


class PostQuerySetMixin:
    def get_queryset(self):
        return (
            Post.post_manager
            .with_related_data()
            .with_coment_count()
        )


class IndexView(PostQuerySetMixin, ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = PUGINATION_NUMBER

    def get_queryset(self):
        return super().get_queryset().published()


class CategoryPostListView(PostQuerySetMixin, ListView):
    template_name = 'blog/category.html'
    model = Category
    paginate_by = PUGINATION_NUMBER

    def get_queryset(self):
        self.category = get_object_or_404(
            self.model,
            slug=self.kwargs['category_slug'],
            is_published=True
        )
        qs = (
            self.category
            .posts
            .with_related_data()
            .with_coment_count()
            .published()
            .filter(
                category__slug=self.kwargs['category_slug'],
            )
        )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context


class ProfileView(PostQuerySetMixin, ListView):
    model = Post
    template_name = 'blog/profile.html'
    paginate_by = PUGINATION_NUMBER

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_object_or_404(
            User, username=self.kwargs['username']
        )
        return context

    def get_queryset(self):
        qs = super().get_queryset().filter(author__username=self.kwargs['username'])
        if self.request.user.is_authenticated and self.request.user.username == self.kwargs['username']:
            return qs
        return qs.published()


class EditProfileView(LoginRequiredMixin, UpdateView):
    model = User
    fields = ('username', 'first_name', 'last_name', 'email')
    template_name = 'blog/user.html'

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        slug = self.request.user.username
        return reverse('blog:profile', args=(slug,))


class PostMixin(PostQuerySetMixin):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'
    condition = Q(
        pub_date__lte=timezone.now(),
        is_published=True,
        category__is_published=True
    )

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            pk=self.kwargs['post_id']
        )

    def get_success_url(self):
        slug = self.request.user.username
        return reverse('blog:profile', args=(slug,))

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostDetailView(PostMixin, DetailView):
    template_name = 'blog/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['post'] = self.get_object()
        context['form'] = CommentsForm()
        context['comments'] = self.get_object().comments.select_related('author')
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            self.condition |= Q(author_id=self.request.user.id)
        return qs.filter(self.condition)


class EditPostView(PostMixin, LoginRequiredMixin, OnlyAuthorMixin, UpdateView):
    def dispatch(self, request, *args, **kwargs):
        if self.get_object().author != self.request.user:
            return redirect(
                'blog:post_detail',
                self.kwargs.get('post_id')
            )
        return super().dispatch(request, *args, **kwargs)


class DeletePostView(PostMixin, LoginRequiredMixin, OnlyAuthorMixin, DeleteView):
    pass


class CreatePostView(PostMixin, LoginRequiredMixin, CreateView):
    pass


class CommentMixin(LoginRequiredMixin):
    model = Comments
    form_class = CommentsForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment'] = self.get_object()
        return context

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = get_object_or_404(Post, pk=self.kwargs['post_id'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.kwargs['post_id']])


class CommentCreateView(CommentMixin, CreateView):
    pass


class CommentDeleteView(CommentMixin, OnlyAuthorMixin, DeleteView):
    pass


class CommentEditView(CommentMixin, OnlyAuthorMixin, UpdateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment'] = self.get_object()
        return context
